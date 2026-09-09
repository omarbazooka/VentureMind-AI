from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.decision import (
    DecisionConfidence,
    DecisionLineageKind,
    DecisionLineageReference,
    FinalDecisionAnalysis,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.schemas.finance import FinancialInputName, FinancialMetricName
from app.schemas.validation import ValidationSeverity, ValidationStatus


class DecisionGroundingError(ValueError):
    pass


def decision_upstream_stage_run_ids(
    context: InvestmentCommitteeContext,
) -> dict[AnalysisStage, object]:
    if not context.research_stage_run_ids:
        return {}
    return {
        **context.research_stage_run_ids,
        AnalysisStage.BUSINESS_STRATEGY: context.business_strategy_stage_run_id,
        AnalysisStage.FINANCE: context.finance_stage_run_id,
        AnalysisStage.DECISION_ANALYTICS: context.analytics_stage_run_id,
        AnalysisStage.RISK: context.risk_stage_run_id,
        AnalysisStage.INDEPENDENT_VALIDATION: context.validation_stage_run_id,
    }


def _evidence_stages_by_id(
    context: InvestmentCommitteeContext,
) -> dict[str, set[AnalysisStage]]:
    stages_by_id: dict[str, set[AnalysisStage]] = {}
    for stage, analysis in (
        (AnalysisStage.MARKET_RESEARCH, context.market_analysis),
        (AnalysisStage.COMPETITOR_INTELLIGENCE, context.competitor_analysis),
        (AnalysisStage.CUSTOMER_INTELLIGENCE, context.customer_analysis),
    ):
        if analysis is None:
            continue
        for source in analysis.evidence_sources:
            stages_by_id.setdefault(source.source_id, set()).add(stage)
    return stages_by_id


def _collect_evidence_ids(context: InvestmentCommitteeContext) -> set[str]:
    return set(_evidence_stages_by_id(context))


def _collect_financial_metrics(context: InvestmentCommitteeContext) -> set[FinancialMetricName]:
    metrics: set[FinancialMetricName] = set()
    for scenario in (
        context.finance_bundle.base,
        context.finance_bundle.upside,
        context.finance_bundle.downside,
    ):
        metrics.update(metric.metric_name for metric in scenario.metrics)
    return metrics


def _collect_decision_kpis(context: InvestmentCommitteeContext) -> set[DecisionKPIName]:
    return {kpi.metric_name for kpi in context.decision_analytics.kpis}


def _collect_sensitivity_inputs(context: InvestmentCommitteeContext) -> set[FinancialInputName]:
    if context.decision_analytics.sensitivity is None:
        return set()
    return {
        item.input_name
        for item in context.decision_analytics.sensitivity.inputs
    }


def _normalize_lineage_reference(
    *,
    reference: DecisionLineageReference,
    context: InvestmentCommitteeContext,
) -> DecisionLineageReference:
    if reference.kind == DecisionLineageKind.PROFILE_FIELD:
        if reference.value not in context.profile_snapshot.profile_data:
            raise DecisionGroundingError(
                f"Final Decision references unknown profile field: {reference.value}"
            )
        return reference

    if reference.kind == DecisionLineageKind.EVIDENCE_SOURCE:
        stages_by_id = _evidence_stages_by_id(context)
        available_stages = stages_by_id.get(reference.value)
        if not available_stages:
            raise DecisionGroundingError(
                f"Final Decision references unknown evidence source: {reference.value}"
            )
        if reference.stage is not None and reference.stage not in available_stages:
            raise DecisionGroundingError(
                "Final Decision evidence source is attributed to the wrong research stage"
            )
        selected_stage = reference.stage or sorted(
            available_stages,
            key=lambda stage: stage.value,
        )[0]
        return reference.model_copy(update={"stage": selected_stage})

    if reference.kind == DecisionLineageKind.STAGE_RESULT:
        stage = reference.stage
        if stage is None:
            raise DecisionGroundingError("STAGE_RESULT lineage is missing its stage")
        if stage in {
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        } and context.research_stage_run_ids:
            if stage not in set(context.research_gate.insufficient_stages):
                raise DecisionGroundingError(
                    "Research stage-only lineage is not concrete enough; cite an exact evidence source"
                )
        return reference

    if reference.kind == DecisionLineageKind.FINANCIAL_METRIC:
        try:
            metric = FinancialMetricName(reference.value)
        except ValueError as exc:
            raise DecisionGroundingError(
                f"Final Decision references unknown financial metric: {reference.value}"
            ) from exc
        if metric not in _collect_financial_metrics(context):
            raise DecisionGroundingError(
                f"Final Decision references unavailable financial metric: {reference.value}"
            )
        return reference

    if reference.kind == DecisionLineageKind.DECISION_KPI:
        try:
            kpi = DecisionKPIName(reference.value)
        except ValueError as exc:
            raise DecisionGroundingError(
                f"Final Decision references unknown Decision KPI: {reference.value}"
            ) from exc
        if kpi not in _collect_decision_kpis(context):
            raise DecisionGroundingError(
                f"Final Decision references unavailable Decision KPI: {reference.value}"
            )
        return reference

    if reference.kind == DecisionLineageKind.SENSITIVITY_INPUT:
        try:
            input_name = FinancialInputName(reference.value)
        except ValueError as exc:
            raise DecisionGroundingError(
                f"Final Decision references unknown sensitivity input: {reference.value}"
            ) from exc
        if input_name not in _collect_sensitivity_inputs(context):
            raise DecisionGroundingError(
                f"Final Decision references unavailable sensitivity input: {reference.value}"
            )
        return reference

    if reference.kind == DecisionLineageKind.RISK:
        valid_titles = {risk.title for risk in context.risk_analysis.risks}
        if reference.value not in valid_titles:
            raise DecisionGroundingError(
                f"Final Decision references unknown risk: {reference.value}"
            )
        return reference

    if reference.kind == DecisionLineageKind.VALIDATION_ISSUE:
        valid_categories = {
            issue.category.value
            for issue in context.validation_analysis.issues
        }
        if reference.value not in valid_categories:
            raise DecisionGroundingError(
                f"Final Decision references unknown validation issue: {reference.value}"
            )
        return reference

    raise DecisionGroundingError(
        f"Unsupported Final Decision lineage kind: {reference.kind.value}"
    )


def _validate_lineage(
    *,
    lineage: list[DecisionLineageReference],
    context: InvestmentCommitteeContext,
) -> list[DecisionLineageReference]:
    if not lineage:
        raise DecisionGroundingError(
            "Final Decision requires at least one concrete supporting lineage reference"
        )
    normalized = [
        _normalize_lineage_reference(reference=reference, context=context)
        for reference in lineage
    ]
    keys = [(ref.kind, ref.value, ref.stage) for ref in normalized]
    if len(keys) != len(set(keys)):
        raise DecisionGroundingError(
            "Final Decision lineage collapses to duplicate authoritative references"
        )
    return normalized


def _apply_policy(
    *,
    decision: VentureDecision,
    confidence: DecisionConfidence,
    context: InvestmentCommitteeContext,
) -> tuple[VentureDecision, DecisionConfidence, list[str]]:
    validation_status = context.validation_analysis.status
    if validation_status == ValidationStatus.FAILED or not context.validation_analysis.can_proceed:
        raise DecisionGroundingError(
            "Investment Committee cannot issue a decision from a Validation result that blocks progression"
        )

    insufficient_research = bool(context.research_gate.insufficient_stages)
    has_high_validation_issue = any(
        issue.severity in {ValidationSeverity.HIGH, ValidationSeverity.CRITICAL}
        for issue in context.validation_analysis.issues
    )
    validation_warned = validation_status in {
        ValidationStatus.PASSED_WITH_WARNINGS,
        ValidationStatus.INSUFFICIENT_EVIDENCE,
    }

    adjusted_confidence = confidence
    if (insufficient_research or validation_warned) and adjusted_confidence == DecisionConfidence.HIGH:
        adjusted_confidence = DecisionConfidence.MEDIUM

    adjusted_decision = decision
    if (
        adjusted_decision == VentureDecision.GO
        and (
            insufficient_research
            or validation_status == ValidationStatus.INSUFFICIENT_EVIDENCE
            or has_high_validation_issue
        )
    ):
        adjusted_decision = VentureDecision.CONDITIONAL_GO

    generated_limitations: list[str] = []
    if insufficient_research:
        generated_limitations.append(
            "Final decision is bounded by insufficient research evidence in upstream stages."
        )
    if validation_status == ValidationStatus.INSUFFICIENT_EVIDENCE:
        generated_limitations.append(
            "Independent Validation reported insufficient evidence; confidence and recommendation are capped accordingly."
        )
    elif has_high_validation_issue:
        generated_limitations.append(
            "Independent Validation reported high-severity concerns that constrain the final recommendation."
        )

    return adjusted_decision, adjusted_confidence, generated_limitations


def validate_grounded_decision(
    *,
    draft: FinalDecisionDraft,
    context: InvestmentCommitteeContext,
) -> FinalDecisionAnalysis:
    # Evaluate deterministic decision guardrails before lineage validation so a
    # packet that is not legally allowed to reach the Committee fails for the
    # authoritative state reason rather than a secondary citation defect.
    decision, confidence, generated_limitations = _apply_policy(
        decision=draft.decision,
        confidence=draft.confidence,
        context=context,
    )

    normalized_lineage = _validate_lineage(
        lineage=draft.supporting_evidence_lineage,
        context=context,
    )

    limitations = list(draft.limitations)
    for limitation in generated_limitations:
        if limitation not in limitations:
            limitations.append(limitation)

    return FinalDecisionAnalysis(
        decision=decision,
        confidence=confidence,
        rationale=draft.rationale,
        supporting_evidence_lineage=normalized_lineage,
        strongest_positive_signals=draft.strongest_positive_signals,
        strongest_negative_signals=draft.strongest_negative_signals,
        critical_assumptions=draft.critical_assumptions,
        limitations=limitations,
        what_could_change=draft.what_could_change,
        recommended_next_steps=draft.recommended_next_steps,
        upstream_stage_run_ids=decision_upstream_stage_run_ids(context),
    )


def validate_persisted_decision(
    *,
    analysis: FinalDecisionAnalysis,
    context: InvestmentCommitteeContext,
) -> FinalDecisionAnalysis:
    expected_lineage = decision_upstream_stage_run_ids(context)
    if analysis.upstream_stage_run_ids != expected_lineage:
        raise DecisionGroundingError(
            "Final Decision upstream stage lineage changed before persistence"
        )

    normalized_lineage = _validate_lineage(
        lineage=analysis.supporting_evidence_lineage,
        context=context,
    )
    if normalized_lineage != analysis.supporting_evidence_lineage:
        raise DecisionGroundingError(
            "Persisted Final Decision lineage is not normalized to authoritative references"
        )

    expected_decision, expected_confidence, generated_limitations = _apply_policy(
        decision=analysis.decision,
        confidence=analysis.confidence,
        context=context,
    )
    if analysis.decision != expected_decision:
        raise DecisionGroundingError(
            "Final Decision no longer satisfies deterministic decision guardrails"
        )
    if analysis.confidence != expected_confidence:
        raise DecisionGroundingError(
            "Final Decision confidence no longer satisfies deterministic confidence guardrails"
        )
    for limitation in generated_limitations:
        if limitation not in analysis.limitations:
            raise DecisionGroundingError(
                "Final Decision dropped an authoritative evidence limitation"
            )

    return analysis
