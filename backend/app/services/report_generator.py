from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.report import Report
from app.schemas.analysis import AnalysisStage, AnalysisStageStatus
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.decision import DECISION_UPSTREAM_STAGES, FinalDecisionAnalysis
from app.schemas.finance import (
    FinancialMetricName,
    FinancialScenarioBundle,
)
from app.schemas.report import (
    ReportAnalyticsSection,
    ReportChartData,
    ReportCompetitorSection,
    ReportCustomerSection,
    ReportFinanceSection,
    ReportMarketMetrics,
    ReportMarketSection,
    ReportRiskSection,
    ReportSourceItem,
    ReportStrategySection,
    ReportValidationSection,
    StructuredReport,
)
from app.schemas.research import CompetitorAnalysis, CustomerAnalysis, MarketAnalysis
from app.schemas.risk import RiskAnalysis
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis


class ReportGenerationError(RuntimeError):
    pass


def _extract_metric(metrics: list[Any], metric_name: FinancialMetricName) -> Any | None:
    for metric in metrics:
        name = metric.metric_name if hasattr(metric, "metric_name") else metric.get("metric_name")
        if name == metric_name or name == metric_name.value:
            return metric
    return None


def _metric_value(metric: Any | None) -> Decimal | None:
    if metric is None:
        return None
    value = metric.value if hasattr(metric, "value") else metric.get("value")
    return Decimal(str(value)) if value is not None else None


def _load_completed_result(
    *,
    db: Session,
    analysis_run_id: UUID,
    stage: AnalysisStage,
    stage_run_id: UUID,
) -> AnalysisResult:
    stage_run = db.get(AnalysisStageRun, stage_run_id)
    if stage_run is None:
        raise ReportGenerationError(
            f"Report lineage references a missing {stage.value} stage run"
        )
    if stage_run.analysis_run_id != analysis_run_id:
        raise ReportGenerationError(
            f"Report lineage for {stage.value} belongs to another AnalysisRun"
        )
    if stage_run.stage != stage.value:
        raise ReportGenerationError(
            f"Report lineage stage mismatch for {stage.value}"
        )
    if stage_run.status != AnalysisStageStatus.COMPLETED.value:
        raise ReportGenerationError(
            f"Report requires completed {stage.value} stage lineage"
        )

    result = db.scalar(
        select(AnalysisResult).where(
            AnalysisResult.analysis_run_id == analysis_run_id,
            AnalysisResult.stage_run_id == stage_run_id,
            AnalysisResult.stage == stage.value,
        )
    )
    if result is None:
        raise ReportGenerationError(
            f"Completed {stage.value} lineage has no persisted result"
        )
    return result


def _load_latest_completed_decision(
    *, db: Session, analysis_run_id: UUID
) -> tuple[AnalysisResult, FinalDecisionAnalysis]:
    result = db.scalar(
        select(AnalysisResult)
        .join(
            AnalysisStageRun,
            AnalysisStageRun.id == AnalysisResult.stage_run_id,
        )
        .where(
            AnalysisResult.analysis_run_id == analysis_run_id,
            AnalysisResult.stage == AnalysisStage.INVESTMENT_COMMITTEE.value,
            AnalysisStageRun.analysis_run_id == analysis_run_id,
            AnalysisStageRun.stage == AnalysisStage.INVESTMENT_COMMITTEE.value,
            AnalysisStageRun.status == AnalysisStageStatus.COMPLETED.value,
        )
        .order_by(
            AnalysisStageRun.attempt.desc(),
            AnalysisResult.created_at.desc(),
        )
        .limit(1)
    )
    if result is None:
        raise ReportGenerationError(
            "Cannot generate report before Investment Committee is completed"
        )

    try:
        decision = FinalDecisionAnalysis.model_validate(result.result_data)
    except ValidationError as exc:
        raise ReportGenerationError(
            "Persisted Final Decision is invalid"
        ) from exc

    if set(decision.upstream_stage_run_ids) != DECISION_UPSTREAM_STAGES:
        raise ReportGenerationError(
            "Final Decision does not contain complete upstream stage-run lineage"
        )
    return result, decision


def _build_finance_summary(finance: FinancialScenarioBundle) -> str:
    revenue_metric = _extract_metric(
        finance.base.metrics, FinancialMetricName.REVENUE
    )
    operating_metric = _extract_metric(
        finance.base.metrics, FinancialMetricName.OPERATING_RESULT
    )
    revenue = _metric_value(revenue_metric)
    operating = _metric_value(operating_metric)

    parts = [
        "Financial analysis evaluated the authoritative Base, Upside, and Downside scenarios."
    ]
    if revenue is not None:
        currency = getattr(revenue_metric, "currency", None)
        period = getattr(revenue_metric, "period", None)
        suffix = ""
        if currency:
            suffix += f" {currency}"
        if period:
            suffix += f" / {period.value.lower()}"
        parts.append(f"Base revenue: {revenue}{suffix}.")
    if operating is not None:
        currency = getattr(operating_metric, "currency", None)
        period = getattr(operating_metric, "period", None)
        suffix = ""
        if currency:
            suffix += f" {currency}"
        if period:
            suffix += f" / {period.value.lower()}"
        parts.append(f"Base operating result: {operating}{suffix}.")
    return " ".join(parts)


def _build_chart_data(
    *,
    finance_bundle: FinancialScenarioBundle,
    analytics_result: DecisionAnalyticsResult,
    risk_analysis: RiskAnalysis,
) -> ReportChartData:
    break_even_comparison: list[dict[str, Any]] = []
    sensitivity_ranking: list[dict[str, Any]] = []
    risk_matrix: list[dict[str, Any]] = []

    for scenario_name, scenario in (
        ("BASE", finance_bundle.base),
        ("UPSIDE", finance_bundle.upside),
        ("DOWNSIDE", finance_bundle.downside),
    ):
        break_even_metric = _extract_metric(
            scenario.metrics, FinancialMetricName.BREAK_EVEN_UNITS
        )
        break_even_units = _metric_value(break_even_metric)
        price = scenario.assumptions.selling_price_per_unit.value

        derived_revenue = None
        if break_even_units is not None and price is not None:
            derived_revenue = break_even_units * price

        break_even_comparison.append(
            {
                "scenario": scenario_name,
                "break_even_units": (
                    str(break_even_units)
                    if break_even_units is not None
                    else None
                ),
                "break_even_revenue": (
                    str(derived_revenue)
                    if derived_revenue is not None
                    else None
                ),
                "currency": scenario.assumptions.selling_price_per_unit.currency,
                "period": (
                    break_even_metric.period.value
                    if break_even_metric is not None
                    and getattr(break_even_metric, "period", None) is not None
                    else None
                ),
                "provenance": "CALCULATED_FROM_FINANCE",
            }
        )

    # VentureMind currently has no authoritative month-by-month forecast model.
    # Do not invent a ramp curve in the report layer. This stays empty until a
    # persisted Finance/time-series result explicitly provides monthly values.
    monthly_projections: list[dict[str, Any]] = []

    if analytics_result.sensitivity is not None:
        for item in sorted(
            analytics_result.sensitivity.inputs,
            key=lambda value: value.rank or 10_000,
        ):
            sensitivity_ranking.append(
                {
                    "input_name": item.input_name.value,
                    "rank": item.rank,
                    "shock_percent": str(
                        analytics_result.sensitivity.shock_percent
                    ),
                    "max_abs_ranking_metric_change_percent": (
                        str(item.max_abs_ranking_metric_change_percent)
                        if item.max_abs_ranking_metric_change_percent is not None
                        else None
                    ),
                    "decrease": item.decrease.model_dump(mode="json"),
                    "increase": item.increase.model_dump(mode="json"),
                    "provenance": "CALCULATED",
                }
            )

    for risk in risk_analysis.risks:
        risk_matrix.append(
            {
                "category": risk.category.value,
                "title": risk.title,
                "likelihood": risk.likelihood.value,
                "impact": risk.impact.value,
                "score": risk.risk_score,
                "level": risk.risk_level.value,
                "mitigation_actions": risk.mitigation_actions,
                "monitoring_signals": risk.monitoring_signals,
            }
        )

    return ReportChartData(
        break_even_comparison=break_even_comparison,
        monthly_projections=monthly_projections,
        sensitivity_ranking=sensitivity_ranking,
        risk_matrix=risk_matrix,
    )


def generate_structured_report(
    *, db: Session, analysis_run_id: UUID
) -> tuple[Report, StructuredReport]:
    # Serialize report generation for one AnalysisRun and make retries idempotent.
    run = db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.id == analysis_run_id)
        .with_for_update()
    )
    if run is None:
        raise ReportGenerationError(
            f"AnalysisRun with ID {analysis_run_id} not found"
        )

    existing = db.scalar(
        select(Report)
        .where(Report.analysis_run_id == analysis_run_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    if existing is not None:
        try:
            return existing, StructuredReport.model_validate(existing.report_data)
        except ValidationError as exc:
            raise ReportGenerationError(
                "Existing persisted report is invalid"
            ) from exc

    idea = db.get(Idea, run.idea_id)
    if idea is None:
        raise ReportGenerationError(f"Idea with ID {run.idea_id} not found")

    _, decision = _load_latest_completed_decision(
        db=db, analysis_run_id=analysis_run_id
    )

    exact_results: dict[AnalysisStage, AnalysisResult] = {}
    for stage in DECISION_UPSTREAM_STAGES:
        exact_results[stage] = _load_completed_result(
            db=db,
            analysis_run_id=analysis_run_id,
            stage=stage,
            stage_run_id=decision.upstream_stage_run_ids[stage],
        )

    try:
        market = MarketAnalysis.model_validate(
            exact_results[AnalysisStage.MARKET_RESEARCH].result_data
        )
        competitors = CompetitorAnalysis.model_validate(
            exact_results[AnalysisStage.COMPETITOR_INTELLIGENCE].result_data
        )
        customer = CustomerAnalysis.model_validate(
            exact_results[AnalysisStage.CUSTOMER_INTELLIGENCE].result_data
        )
        strategy = BusinessStrategyAnalysis.model_validate(
            exact_results[AnalysisStage.BUSINESS_STRATEGY].result_data
        )
        finance = FinancialScenarioBundle.model_validate(
            exact_results[AnalysisStage.FINANCE].result_data
        )
        analytics = DecisionAnalyticsResult.model_validate(
            exact_results[AnalysisStage.DECISION_ANALYTICS].result_data
        )
        risk = RiskAnalysis.model_validate(
            exact_results[AnalysisStage.RISK].result_data
        )
        validation = ValidationAnalysis.model_validate(
            exact_results[AnalysisStage.INDEPENDENT_VALIDATION].result_data
        )
    except ValidationError as exc:
        raise ReportGenerationError(
            "An authoritative upstream result is invalid"
        ) from exc

    # Defense in depth: the exact Finance/Analytics and Validation lineage must
    # still agree with the Final Decision packet selected above.
    if analytics.finance_stage_run_id != decision.upstream_stage_run_ids[AnalysisStage.FINANCE]:
        raise ReportGenerationError(
            "Decision Analytics is not grounded in the Finance result selected by Final Decision"
        )
    expected_validation_lineage = {
        stage: stage_run_id
        for stage, stage_run_id in decision.upstream_stage_run_ids.items()
        if stage != AnalysisStage.INDEPENDENT_VALIDATION
    }
    if validation.upstream_stage_run_ids != expected_validation_lineage:
        raise ReportGenerationError(
            "Independent Validation lineage does not match Final Decision lineage"
        )

    sources: list[ReportSourceItem] = []
    seen_source_ids: set[str] = set()
    for stage, analysis in (
        (AnalysisStage.MARKET_RESEARCH, market),
        (AnalysisStage.COMPETITOR_INTELLIGENCE, competitors),
        (AnalysisStage.CUSTOMER_INTELLIGENCE, customer),
    ):
        for source in analysis.evidence_sources:
            if source.source_id in seen_source_ids:
                continue
            seen_source_ids.add(source.source_id)
            sources.append(
                ReportSourceItem(
                    source_id=source.source_id,
                    title=source.title,
                    url=str(source.url) if source.url else None,
                    provenance=source.provenance.value,
                    stage=stage.value,
                )
            )

    market_section = ReportMarketSection(
        summary=market.summary,
        evidence_quality=market.evidence_quality.value,
        findings=[item.model_dump(mode="json") for item in market.findings],
        market_metrics=ReportMarketMetrics(),
        limitations=market.limitations,
    )
    competitor_section = ReportCompetitorSection(
        summary=competitors.summary,
        evidence_quality=competitors.evidence_quality.value,
        competitors=[item.model_dump(mode="json") for item in competitors.competitors],
        findings=[item.model_dump(mode="json") for item in competitors.findings],
        limitations=competitors.limitations,
    )
    customer_section = ReportCustomerSection(
        summary=customer.summary,
        evidence_quality=customer.evidence_quality.value,
        findings=[item.model_dump(mode="json") for item in customer.findings],
        limitations=customer.limitations,
    )
    strategy_section = ReportStrategySection(
        executive_summary=strategy.executive_summary,
        positioning=[item.model_dump(mode="json") for item in strategy.positioning],
        value_proposition=[item.model_dump(mode="json") for item in strategy.value_proposition],
        business_model_implications=[item.model_dump(mode="json") for item in strategy.business_model_implications],
        go_to_market=[item.model_dump(mode="json") for item in strategy.go_to_market],
        strategic_strengths=[item.model_dump(mode="json") for item in strategy.strategic_strengths],
        strategic_weaknesses=[item.model_dump(mode="json") for item in strategy.strategic_weaknesses],
        critical_assumptions=[item.model_dump(mode="json") for item in strategy.critical_assumptions],
        limitations=strategy.limitations,
    )
    finance_section = ReportFinanceSection(
        executive_summary=_build_finance_summary(finance),
        base_scenario=finance.base.model_dump(mode="json"),
        upside_scenario=finance.upside.model_dump(mode="json"),
        downside_scenario=finance.downside.model_dump(mode="json"),
        comparisons=[item.model_dump(mode="json") for item in finance.comparisons],
        limitations=finance.limitations,
    )
    analytics_section = ReportAnalyticsSection(
        kpis=[item.model_dump(mode="json") for item in analytics.kpis],
        scenario_relative_changes=[item.model_dump(mode="json") for item in analytics.scenario_relative_changes],
        sensitivity=(
            analytics.sensitivity.model_dump(mode="json")
            if analytics.sensitivity is not None
            else None
        ),
        limitations=analytics.limitations,
    )
    risk_section = ReportRiskSection(
        executive_summary=risk.executive_summary,
        overall_level=(risk.overall_level.value if risk.overall_level else None),
        risks=[item.model_dump(mode="json") for item in risk.risks],
        limitations=risk.limitations,
    )
    validation_section = ReportValidationSection(
        status=validation.status.value,
        executive_assessment=validation.executive_assessment,
        issues=[item.model_dump(mode="json") for item in validation.issues],
        limitations=validation.limitations,
    )

    chart_data = _build_chart_data(
        finance_bundle=finance,
        analytics_result=analytics,
        risk_analysis=risk,
    )

    latest_version = db.scalar(
        select(Report.version)
        .where(Report.idea_id == run.idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    version = (latest_version or 0) + 1
    report_id = uuid4()
    now = datetime.now(timezone.utc)

    structured_report = StructuredReport(
        id=report_id,
        idea_id=run.idea_id,
        analysis_run_id=analysis_run_id,
        version=version,
        title=f"VentureMind Evaluation: {idea.title}",
        executive_summary=decision.rationale,
        decision=decision,
        profile_summary=run.profile_snapshot.get("profile_data", {}),
        market=market_section,
        competitors=competitor_section,
        customer=customer_section,
        strategy=strategy_section,
        finance=finance_section,
        analytics=analytics_section,
        risk=risk_section,
        validation=validation_section,
        chart_data=chart_data,
        sources=sources,
        created_at=now,
    )

    persisted = Report(
        id=report_id,
        idea_id=run.idea_id,
        analysis_run_id=analysis_run_id,
        version=version,
        report_data=structured_report.model_dump(mode="json"),
        created_at=now,
    )
    db.add(persisted)
    db.flush()
    return persisted, structured_report
