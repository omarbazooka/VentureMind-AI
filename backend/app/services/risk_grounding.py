from app.schemas.analysis import AnalysisStage
from app.schemas.risk import (
    RISK_LEVEL_ORDER,
    RISK_RESEARCH_STAGES,
    GroundedRisk,
    RiskAnalysis,
    RiskDraft,
    RiskDraftAnalysis,
    calculate_risk_score,
    risk_level_for_score,
)
from app.schemas.risk_runtime import RiskAnalysisContext


class RiskGroundingError(RuntimeError):
    pass


def _research_source_ids_by_stage(
    context: RiskAnalysisContext,
) -> dict[AnalysisStage, set[str]]:
    result_by_stage = {
        AnalysisStage.MARKET_RESEARCH: context.market_analysis,
        AnalysisStage.COMPETITOR_INTELLIGENCE: (
            context.competitor_analysis
        ),
        AnalysisStage.CUSTOMER_INTELLIGENCE: (
            context.customer_analysis
        ),
    }

    return {
        stage: {
            source.source_id
            for source in result.evidence_sources
        }
        if result is not None
        else set()
        for stage, result in result_by_stage.items()
    }


def _available_financial_metrics(
    context: RiskAnalysisContext,
):
    metric_names = set()

    for scenario in (
        context.finance_bundle.base,
        context.finance_bundle.upside,
        context.finance_bundle.downside,
    ):
        metric_names.update(
            metric.metric_name
            for metric in scenario.metrics
        )

    return metric_names


def _available_decision_kpis(
    context: RiskAnalysisContext,
):
    return {
        kpi.metric_name
        for kpi in context.decision_analytics.kpis
    }


def _available_sensitivity_inputs(
    context: RiskAnalysisContext,
):
    sensitivity = context.decision_analytics.sensitivity
    if sensitivity is None:
        return set()

    return {
        item.input_name
        for item in sensitivity.inputs
    }


def _validate_risk_lineage(
    *,
    risk: RiskDraft,
    context: RiskAnalysisContext,
) -> None:
    profile_fields = set(
        context.profile_snapshot.profile_data
    )
    unknown_profile_fields = (
        set(risk.profile_fields)
        - profile_fields
    )
    if unknown_profile_fields:
        raise RiskGroundingError(
            "Risk references unknown IdeaProfile fields: "
            f"{sorted(unknown_profile_fields)}"
        )

    available_financial_metrics = (
        _available_financial_metrics(context)
    )
    unknown_financial_metrics = (
        set(risk.financial_metrics)
        - available_financial_metrics
    )
    if unknown_financial_metrics:
        raise RiskGroundingError(
            "Risk references unavailable Finance metrics: "
            f"{sorted(item.value for item in unknown_financial_metrics)}"
        )

    available_decision_kpis = (
        _available_decision_kpis(context)
    )
    unknown_decision_kpis = (
        set(risk.decision_kpis)
        - available_decision_kpis
    )
    if unknown_decision_kpis:
        raise RiskGroundingError(
            "Risk references unavailable Decision Analytics KPIs: "
            f"{sorted(item.value for item in unknown_decision_kpis)}"
        )

    available_sensitivity_inputs = (
        _available_sensitivity_inputs(context)
    )
    unknown_sensitivity_inputs = (
        set(risk.sensitivity_inputs)
        - available_sensitivity_inputs
    )
    if unknown_sensitivity_inputs:
        raise RiskGroundingError(
            "Risk references unavailable sensitivity inputs: "
            f"{sorted(item.value for item in unknown_sensitivity_inputs)}"
        )

    if risk.evidence_source_ids:
        source_ids_by_stage = (
            _research_source_ids_by_stage(context)
        )
        declared_research_stages = (
            set(risk.supporting_stages)
            & RISK_RESEARCH_STAGES
        )
        allowed_source_ids = set()
        for stage in declared_research_stages:
            allowed_source_ids.update(
                source_ids_by_stage[stage]
            )

        unknown_source_ids = (
            set(risk.evidence_source_ids)
            - allowed_source_ids
        )
        if unknown_source_ids:
            raise RiskGroundingError(
                "Risk references evidence source IDs that are not present "
                "in its declared research supporting stages: "
                f"{sorted(unknown_source_ids)}"
            )


def _ground_risk(
    *,
    risk: RiskDraft,
    context: RiskAnalysisContext,
) -> GroundedRisk:
    _validate_risk_lineage(
        risk=risk,
        context=context,
    )

    score = calculate_risk_score(
        risk.likelihood,
        risk.impact,
    )
    level = risk_level_for_score(score)

    return GroundedRisk(
        **risk.model_dump(),
        risk_score=score,
        risk_level=level,
    )


def _bounded_limitations(
    *,
    draft_limitations: list[str],
    context: RiskAnalysisContext,
) -> list[str]:
    candidates = list(draft_limitations)
    candidates.extend(
        (
            "Research Evidence Gate marked "
            f"{stage.value} as INSUFFICIENT_EVIDENCE."
        )
        for stage in context.research_gate.insufficient_stages
    )

    unique: list[str] = []
    seen: set[str] = set()
    for limitation in candidates:
        normalized = limitation.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)

    if len(unique) <= 30:
        return unique

    return [
        *unique[:29],
        (
            "Additional Risk limitations were omitted after reaching "
            "the structured limit."
        ),
    ]


def finalize_risk_analysis(
    *,
    draft: RiskDraftAnalysis,
    context: RiskAnalysisContext,
) -> RiskAnalysis:
    grounded_risks = [
        _ground_risk(
            risk=risk,
            context=context,
        )
        for risk in draft.risks
    ]

    grounded_risks.sort(
        key=lambda risk: risk.risk_score,
        reverse=True,
    )

    overall_level = (
        max(
            (risk.risk_level for risk in grounded_risks),
            key=lambda level: RISK_LEVEL_ORDER[level],
        )
        if grounded_risks
        else None
    )

    return RiskAnalysis(
        executive_summary=draft.executive_summary,
        risks=grounded_risks,
        overall_level=overall_level,
        limitations=_bounded_limitations(
            draft_limitations=draft.limitations,
            context=context,
        ),
    )
