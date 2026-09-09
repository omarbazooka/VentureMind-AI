from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import FinancialInputName, FinancialMetricName
from app.schemas.validation import (
    VALIDATION_RESEARCH_STAGES,
    ValidationAnalysis,
    ValidationDraft,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStatus,
)
from app.schemas.validation_runtime import ValidationAnalysisContext


class ValidationGroundingError(ValueError):
    pass


def _collect_valid_evidence_ids(context: ValidationAnalysisContext) -> set[str]:
    evidence_ids: set[str] = set()
    for analysis in (
        context.market_analysis,
        context.competitor_analysis,
        context.customer_analysis,
    ):
        if analysis is None:
            continue
        for source in analysis.evidence_sources:
            evidence_ids.add(source.source_id)
    return evidence_ids


def _collect_financial_metrics(context: ValidationAnalysisContext) -> set[FinancialMetricName]:
    metrics: set[FinancialMetricName] = set()
    for scenario in (
        context.finance_bundle.base,
        context.finance_bundle.upside,
        context.finance_bundle.downside,
    ):
        metrics.update(metric.metric_name for metric in scenario.metrics)
    return metrics


def _collect_decision_kpis(context: ValidationAnalysisContext) -> set[DecisionKPIName]:
    return {kpi.metric_name for kpi in context.decision_analytics.kpis}


def _collect_sensitivity_inputs(context: ValidationAnalysisContext) -> set[FinancialInputName]:
    if context.decision_analytics.sensitivity is None:
        return set()
    return {
        item.input_name
        for item in context.decision_analytics.sensitivity.inputs
    }


def _collect_risk_titles(context: ValidationAnalysisContext) -> set[str]:
    return {risk.title for risk in context.risk_analysis.risks}


def validation_upstream_stage_run_ids(
    context: ValidationAnalysisContext,
) -> dict[AnalysisStage, object]:
    if not context.research_stage_run_ids:
        return {}
    return {
        **context.research_stage_run_ids,
        AnalysisStage.BUSINESS_STRATEGY: context.business_strategy_stage_run_id,
        AnalysisStage.FINANCE: context.finance_stage_run_id,
        AnalysisStage.DECISION_ANALYTICS: context.analytics_stage_run_id,
        AnalysisStage.RISK: context.risk_stage_run_id,
    }


def _validate_issue_grounding(
    *,
    issue: ValidationIssue,
    context: ValidationAnalysisContext,
) -> None:
    valid_profile_fields = set(context.profile_snapshot.profile_data)
    valid_evidence_ids = _collect_valid_evidence_ids(context)
    valid_financial_metrics = _collect_financial_metrics(context)
    valid_decision_kpis = _collect_decision_kpis(context)
    valid_sensitivity_inputs = _collect_sensitivity_inputs(context)
    valid_risk_titles = _collect_risk_titles(context)

    invalid_profile_fields = set(issue.profile_fields) - valid_profile_fields
    if invalid_profile_fields:
        raise ValidationGroundingError(
            "Validation issue references non-existent profile fields: "
            + ", ".join(sorted(invalid_profile_fields))
        )

    invalid_evidence = set(issue.evidence_ids) - valid_evidence_ids
    if invalid_evidence:
        raise ValidationGroundingError(
            "Validation issue references non-existent evidence ID: "
            + ", ".join(sorted(invalid_evidence))
        )

    invalid_metrics = set(issue.financial_metrics) - valid_financial_metrics
    if invalid_metrics:
        raise ValidationGroundingError(
            "Validation issue references unavailable financial metrics: "
            + ", ".join(sorted(metric.value for metric in invalid_metrics))
        )

    invalid_kpis = set(issue.decision_kpis) - valid_decision_kpis
    if invalid_kpis:
        raise ValidationGroundingError(
            "Validation issue references unavailable Decision Analytics KPIs: "
            + ", ".join(sorted(kpi.value for kpi in invalid_kpis))
        )

    invalid_sensitivity = set(issue.sensitivity_inputs) - valid_sensitivity_inputs
    if invalid_sensitivity:
        raise ValidationGroundingError(
            "Validation issue references unavailable sensitivity inputs: "
            + ", ".join(sorted(item.value for item in invalid_sensitivity))
        )

    invalid_risk_titles = set(issue.risk_titles) - valid_risk_titles
    if invalid_risk_titles:
        raise ValidationGroundingError(
            "Validation issue references non-existent risks: "
            + ", ".join(sorted(invalid_risk_titles))
        )

    concrete_lineage = any(
        (
            issue.profile_fields,
            issue.evidence_ids,
            issue.financial_metrics,
            issue.decision_kpis,
            issue.sensitivity_inputs,
            issue.risk_titles,
        )
    )
    if not concrete_lineage:
        research_stages = set(issue.affected_stages) & VALIDATION_RESEARCH_STAGES
        insufficient = set(context.research_gate.insufficient_stages)
        if not (
            issue.category == ValidationIssueCategory.MISSING_EVIDENCE
            and research_stages
            and research_stages.issubset(insufficient)
        ):
            raise ValidationGroundingError(
                "Stage-only validation grounding is only allowed for research "
                "MISSING_EVIDENCE issues that match the Research Evidence Gate"
            )


def _derive_policy(
    *,
    issues: list[ValidationIssue],
    context: ValidationAnalysisContext,
) -> tuple[ValidationStatus, bool, list[AnalysisStage], list[str]]:
    has_critical = any(
        issue.severity == ValidationSeverity.CRITICAL
        for issue in issues
    )
    has_high = any(
        issue.severity == ValidationSeverity.HIGH
        for issue in issues
    )
    insufficient_research = bool(context.research_gate.insufficient_stages)

    generated_limitations = [
        f"Research for {stage.value} was flagged as insufficient."
        for stage in context.research_gate.insufficient_stages
    ]

    # Day 9 is a validation gate, not the general re-analysis engine. Critical
    # findings block progression; Day 12 owns safe dependency invalidation and
    # targeted re-analysis. Keeping retry_stages empty prevents stale in-run
    # retries from accidentally reusing old downstream results.
    retry_stages: list[AnalysisStage] = []

    if has_critical:
        return ValidationStatus.FAILED, False, retry_stages, generated_limitations
    if insufficient_research:
        return (
            ValidationStatus.INSUFFICIENT_EVIDENCE,
            True,
            retry_stages,
            generated_limitations,
        )
    if has_high or issues:
        return (
            ValidationStatus.PASSED_WITH_WARNINGS,
            True,
            retry_stages,
            generated_limitations,
        )
    return ValidationStatus.PASSED, True, retry_stages, generated_limitations


def validate_grounded_validation_analysis(
    *,
    draft: ValidationDraft,
    context: ValidationAnalysisContext,
) -> ValidationAnalysis:
    validated_issues: list[ValidationIssue] = []
    for issue in draft.issues:
        _validate_issue_grounding(issue=issue, context=context)
        validated_issues.append(issue)

    status, can_proceed, retry_stages, generated_limitations = _derive_policy(
        issues=validated_issues,
        context=context,
    )

    limitations = list(draft.limitations)
    for limitation in generated_limitations:
        if limitation not in limitations:
            limitations.append(limitation)

    return ValidationAnalysis(
        status=status,
        executive_assessment=draft.executive_assessment,
        issues=validated_issues,
        can_proceed=can_proceed,
        retry_stages=retry_stages,
        limitations=limitations,
        upstream_stage_run_ids=validation_upstream_stage_run_ids(context),
    )


def validate_persisted_validation_analysis(
    *,
    analysis: ValidationAnalysis,
    context: ValidationAnalysisContext,
) -> ValidationAnalysis:
    expected_lineage = validation_upstream_stage_run_ids(context)
    if analysis.upstream_stage_run_ids != expected_lineage:
        raise ValidationGroundingError(
            "Validation upstream stage lineage changed before persistence"
        )

    for issue in analysis.issues:
        _validate_issue_grounding(issue=issue, context=context)

    status, can_proceed, retry_stages, generated_limitations = _derive_policy(
        issues=analysis.issues,
        context=context,
    )
    if analysis.status != status:
        raise ValidationGroundingError(
            "Validation status no longer matches the authoritative upstream context"
        )
    if analysis.can_proceed != can_proceed:
        raise ValidationGroundingError(
            "Validation progression decision no longer matches authoritative policy"
        )
    if analysis.retry_stages != retry_stages:
        raise ValidationGroundingError(
            "Validation retry policy was not derived from authoritative application rules"
        )
    for limitation in generated_limitations:
        if limitation not in analysis.limitations:
            raise ValidationGroundingError(
                "Validation result dropped an authoritative evidence limitation"
            )

    return analysis
