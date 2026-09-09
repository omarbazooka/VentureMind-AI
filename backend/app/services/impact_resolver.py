import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.models.report import Report
from app.schemas.analysis import AnalysisRunStatus, AnalysisStage, AnalysisStageStatus
from app.schemas.reanalysis import (
    MetricComparisonItem,
    ReanalysisRequest,
    ReanalysisResponse,
    ReportComparisonResponse,
)

logger = logging.getLogger(__name__)

# Sequential pipeline stages in execution order
PIPELINE_STAGES: list[AnalysisStage] = [
    AnalysisStage.MARKET_RESEARCH,
    AnalysisStage.COMPETITOR_INTELLIGENCE,
    AnalysisStage.CUSTOMER_INTELLIGENCE,
    AnalysisStage.BUSINESS_STRATEGY,
    AnalysisStage.FINANCE,
    AnalysisStage.DECISION_ANALYTICS,
    AnalysisStage.RISK,
    AnalysisStage.INDEPENDENT_VALIDATION,
    AnalysisStage.INVESTMENT_COMMITTEE,
]

FINANCIAL_PROFILE_FIELDS = {
    "idea_pricing",
    "pricing_model",
    "starting_cash",
    "cost_structure",
    "revenue_model",
    "unit_economics",
}

RESEARCH_PROFILE_FIELDS = {
    "idea_description",
    "target_customers",
    "target_country",
    "problem_statement",
    "solution_concept",
    "industry",
    "competitors",
}


def resolve_stage_invalidation(
    target_stage: AnalysisStage | None = None,
    changed_profile_fields: set[str] | None = None,
) -> tuple[list[AnalysisStage], list[AnalysisStage]]:
    """Determine which stages are invalidated and which can be reused.

    Returns:
        (invalidated_stages, reused_stages)
    """
    if target_stage is None:
        if changed_profile_fields:
            if any(f in RESEARCH_PROFILE_FIELDS for f in changed_profile_fields):
                target_stage = AnalysisStage.MARKET_RESEARCH
            elif any(f in FINANCIAL_PROFILE_FIELDS for f in changed_profile_fields):
                target_stage = AnalysisStage.FINANCE
            else:
                target_stage = AnalysisStage.MARKET_RESEARCH
        else:
            target_stage = AnalysisStage.MARKET_RESEARCH

    # Find index of target stage in pipeline
    # Note: MARKET, COMPETITOR, and CUSTOMER are all at the same conceptual research tier
    if target_stage in (
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ):
        split_idx = 0
    else:
        split_idx = PIPELINE_STAGES.index(target_stage)

    reused_stages = PIPELINE_STAGES[:split_idx]
    invalidated_stages = PIPELINE_STAGES[split_idx:]

    return invalidated_stages, reused_stages


def get_latest_completed_run_and_results(
    db: Session,
    idea_id: UUID,
) -> tuple[AnalysisRun | None, dict[AnalysisStage, AnalysisResult]]:
    """Fetch the latest completed AnalysisRun and its associated AnalysisResult objects."""
    run = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.idea_id == idea_id,
            AnalysisRun.status == AnalysisRunStatus.COMPLETED.value,
        )
        .order_by(AnalysisRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return None, {}

    stage_runs = list(
        db.scalars(
            select(AnalysisStageRun)
            .where(AnalysisStageRun.analysis_run_id == run.id)
        ).all()
    )

    stage_run_ids = [sr.id for sr in stage_runs]
    results = list(
        db.scalars(
            select(AnalysisResult)
            .where(AnalysisResult.stage_run_id.in_(stage_run_ids))
        ).all()
    )

    results_by_stage: dict[AnalysisStage, AnalysisResult] = {}
    stage_by_id = {sr.id: sr.stage for sr in stage_runs}
    for r in results:
        stage_name = stage_by_id.get(r.stage_run_id)
        if stage_name:
            try:
                stage_enum = AnalysisStage(stage_name)
                results_by_stage[stage_enum] = r
            except ValueError:
                pass

    return run, results_by_stage


def trigger_targeted_reanalysis(
    db: Session,
    idea_id: UUID,
    request: ReanalysisRequest,
) -> ReanalysisResponse:
    """Create a new authoritative AnalysisRun and Profile version for targeted reanalysis.

    Preserves execution history: does NOT clone old AnalysisStageRun rows.
    Explicitly tracks reused upstream stage result IDs in lineage metadata.
    """
    idea = db.get(Idea, idea_id)
    if idea is None:
        raise ValueError(f"Idea {idea_id} not found")

    prev_run, prev_results = get_latest_completed_run_and_results(db, idea_id)
    if prev_run is None:
        raise ValueError(f"Cannot reanalyze idea {idea_id}: no completed prior analysis exists.")

    # 1. Determine profile updates & create new profile version if requested
    latest_profile = db.scalar(
        select(IdeaProfile)
        .where(IdeaProfile.idea_id == idea_id)
        .order_by(IdeaProfile.version.desc())
        .limit(1)
    )
    if latest_profile is None:
        raise ValueError(f"No IdeaProfile found for idea {idea_id}")

    changed_fields: set[str] = set()
    new_version = latest_profile.version
    active_profile = latest_profile

    if request.profile_updates:
        new_version = latest_profile.version + 1
        updated_data = dict(latest_profile.profile_data or {})
        updated_metadata = dict(latest_profile.profile_metadata or {})

        for k, v in request.profile_updates.items():
            updated_data[k] = v
            updated_metadata[k] = {
                "provenance": "USER",
                "source": "reanalysis_update",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            changed_fields.add(k)

        new_profile = IdeaProfile(
            idea_id=idea_id,
            version=new_version,
            readiness=latest_profile.readiness,
            profile_data=updated_data,
            profile_metadata=updated_metadata,
            unknown_fields=latest_profile.unknown_fields,
        )
        db.add(new_profile)
        db.flush()
        active_profile = new_profile

    # 2. Resolve stage invalidation & reused stage results
    invalidated_stages, reused_stages = resolve_stage_invalidation(
        target_stage=request.target_stage,
        changed_profile_fields=changed_fields,
    )

    reused_result_ids: dict[str, str] = {}
    for stage in reused_stages:
        if stage in prev_results:
            reused_result_ids[stage.value] = str(prev_results[stage].id)

    # 3. Create new authoritative AnalysisRun tracking lineage without cloning old runs
    new_run = AnalysisRun(
        idea_id=idea_id,
        profile_id=active_profile.id,
        profile_version=active_profile.version,
        profile_snapshot={
            "readiness": active_profile.readiness,
            "profile_data": active_profile.profile_data,
            "profile_metadata": active_profile.profile_metadata,
            "unknown_fields": active_profile.unknown_fields,
            "lineage": {
                "source_run_id": str(prev_run.id),
                "reused_stages": [s.value for s in reused_stages],
                "invalidated_stages": [s.value for s in invalidated_stages],
                "reused_stage_result_ids": reused_result_ids,
                "reanalysis_reason": request.reason,
            },
        },
        status=AnalysisRunStatus.QUEUED.value,
    )
    db.add(new_run)
    db.flush()

    db.commit()

    return ReanalysisResponse(
        idea_id=idea_id,
        new_analysis_run_id=new_run.id,
        new_profile_version=active_profile.version,
        invalidated_stages=invalidated_stages,
        reused_stages=reused_stages,
        reused_result_ids=reused_result_ids,
        status=AnalysisRunStatus.QUEUED,
    )


def compare_report_versions(
    db: Session,
    idea_id: UUID,
    v1_version: int,
    v2_version: int,
) -> ReportComparisonResponse:
    """Compare two structured report versions for an idea and generate delta metrics."""
    reports = list(
        db.scalars(
            select(Report)
            .where(
                Report.idea_id == idea_id,
                Report.version.in_([v1_version, v2_version]),
            )
        ).all()
    )
    report_map = {r.version: r for r in reports}

    if v1_version not in report_map:
        raise ValueError(f"Report version {v1_version} not found for idea {idea_id}")
    if v2_version not in report_map:
        raise ValueError(f"Report version {v2_version} not found for idea {idea_id}")

    r1 = report_map[v1_version]
    r2 = report_map[v2_version]

    d1 = r1.report_data or {}
    d2 = r2.report_data or {}

    # Decision comparison
    dec1 = d1.get("investment_committee", {}).get("decision")
    dec2 = d2.get("investment_committee", {}).get("decision")
    conf1 = d1.get("investment_committee", {}).get("confidence")
    conf2 = d2.get("investment_committee", {}).get("confidence")

    decision_comparison = {
        "v1_decision": dec1,
        "v2_decision": dec2,
        "v1_confidence": conf1,
        "v2_confidence": conf2,
        "changed": dec1 != dec2,
    }

    # Financial comparison
    f1 = d1.get("financial_analysis", {})
    f2 = d2.get("financial_analysis", {})

    def _extract_metric(fin: dict[str, Any], name: str) -> Any:
        metrics = fin.get("key_metrics", {})
        if name in metrics:
            val = metrics[name]
            if isinstance(val, dict):
                return val.get("value")
            return val
        return None

    financial_metrics_to_compare = [
        "net_present_value",
        "internal_rate_of_return",
        "payback_period_months",
        "monthly_burn_rate",
        "break_even_units",
    ]

    financial_diffs: list[MetricComparisonItem] = []
    for metric_name in financial_metrics_to_compare:
        v1_val = _extract_metric(f1, metric_name)
        v2_val = _extract_metric(f2, metric_name)

        delta = None
        direction = "UNCHANGED"

        if v1_val is not None and v2_val is not None:
            try:
                num1 = float(v1_val)
                num2 = float(v2_val)
                diff = num2 - num1
                delta = round(diff, 2)
                if diff > 0:
                    direction = "UP"
                elif diff < 0:
                    direction = "DOWN"
                else:
                    direction = "UNCHANGED"
            except (ValueError, TypeError):
                direction = "CHANGED" if v1_val != v2_val else "UNCHANGED"
        elif v1_val is None and v2_val is not None:
            direction = "NEW"
        elif v1_val is not None and v2_val is None:
            direction = "REMOVED"

        financial_diffs.append(
            MetricComparisonItem(
                metric_name=metric_name,
                v1_value=v1_val,
                v2_value=v2_val,
                delta=delta,
                direction=direction,
            )
        )

    # Risk comparison
    risk1 = d1.get("risk_assessment", {})
    risk2 = d2.get("risk_assessment", {})
    r_list1 = risk1.get("identified_risks", []) or []
    r_list2 = risk2.get("identified_risks", []) or []

    high_risks1 = [r for r in r_list1 if isinstance(r, dict) and r.get("impact") == "HIGH"]
    high_risks2 = [r for r in r_list2 if isinstance(r, dict) and r.get("impact") == "HIGH"]

    risk_comparison = {
        "v1_total_risks": len(r_list1),
        "v2_total_risks": len(r_list2),
        "v1_high_risks": len(high_risks1),
        "v2_high_risks": len(high_risks2),
        "net_risk_change": len(r_list2) - len(r_list1),
    }

    # Lineage comparison from run snapshot
    run2 = db.get(AnalysisRun, r2.analysis_run_id)
    lineage_meta = (
        run2.profile_snapshot.get("lineage", {})
        if run2 and run2.profile_snapshot
        else {}
    )

    lineage_comparison = {
        "reused_stages": lineage_meta.get("reused_stages", []),
        "invalidated_stages": lineage_meta.get("invalidated_stages", []),
        "source_run_id": lineage_meta.get("source_run_id"),
        "reason": lineage_meta.get("reanalysis_reason"),
    }

    # Executive takeaway synthesis
    takeaway_parts = []
    if decision_comparison["changed"]:
        takeaway_parts.append(
            f"Venture decision shifted from {dec1} (v{v1_version}) to {dec2} (v{v2_version})."
        )
    else:
        takeaway_parts.append(
            f"Venture decision remained {dec2} across both versions."
        )

    if risk_comparison["net_risk_change"] < 0:
        takeaway_parts.append(
            f"Risk profile improved with {abs(risk_comparison['net_risk_change'])} fewer identified risks."
        )
    elif risk_comparison["net_risk_change"] > 0:
        takeaway_parts.append(
            f"Risk profile identified {risk_comparison['net_risk_change']} additional risk factors."
        )

    executive_takeaway = " ".join(takeaway_parts)

    return ReportComparisonResponse(
        idea_id=idea_id,
        v1_report_id=r1.id,
        v1_version=v1_version,
        v2_report_id=r2.id,
        v2_version=v2_version,
        v1_analysis_run_id=r1.analysis_run_id,
        v2_analysis_run_id=r2.analysis_run_id,
        decision_comparison=decision_comparison,
        financial_comparison=financial_diffs,
        risk_comparison=risk_comparison,
        lineage_comparison=lineage_comparison,
        executive_takeaway=executive_takeaway,
    )
