from app.schemas.analysis import AnalysisStage
from app.schemas.validation import (
    ValidationAnalysis,
    ValidationDraft,
    ValidationIssue,
    ValidationSeverity,
    ValidationStatus,
)
from app.schemas.validation_runtime import ValidationAnalysisContext


class ValidationGroundingError(ValueError):
    pass


def _collect_valid_evidence_ids(context: ValidationAnalysisContext) -> set[str]:
    evidence_ids: set[str] = set()
    if context.market_analysis and hasattr(context.market_analysis, "evidence_sources"):
        for source in context.market_analysis.evidence_sources:
            evidence_ids.add(source.source_id)
    if context.competitor_analysis and hasattr(context.competitor_analysis, "evidence_sources"):
        for source in context.competitor_analysis.evidence_sources:
            evidence_ids.add(source.source_id)
    if context.customer_analysis and hasattr(context.customer_analysis, "evidence_sources"):
        for source in context.customer_analysis.evidence_sources:
            evidence_ids.add(source.source_id)
    return evidence_ids


def validate_grounded_validation_analysis(
    *,
    draft: ValidationDraft,
    context: ValidationAnalysisContext,
) -> ValidationAnalysis:
    valid_evidence_ids = _collect_valid_evidence_ids(context)
    allowed_stages = {
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
        AnalysisStage.BUSINESS_STRATEGY,
        AnalysisStage.FINANCE,
        AnalysisStage.DECISION_ANALYTICS,
        AnalysisStage.RISK,
    }

    validated_issues: list[ValidationIssue] = []
    has_critical = False
    has_high = False

    for issue in draft.issues:
        for stage in issue.affected_stages:
            if stage not in allowed_stages:
                raise ValidationGroundingError(
                    f"Validation issue references unsupported stage: {stage.value}"
                )

        for ev_id in issue.evidence_ids:
            if ev_id not in valid_evidence_ids:
                raise ValidationGroundingError(
                    f"Validation issue references non-existent evidence ID: {ev_id}"
                )

        if issue.severity == ValidationSeverity.CRITICAL:
            has_critical = True
        elif issue.severity == ValidationSeverity.HIGH:
            has_high = True

        validated_issues.append(issue)

    # Determine status and can_proceed deterministically
    insufficient_research = bool(context.research_gate.insufficient_stages)
    limitations = list(draft.limitations)

    if insufficient_research:
        for stage in context.research_gate.insufficient_stages:
            limitations.append(
                f"Research for {stage.value} was flagged as insufficient."
            )

    # Deterministic retry policy: map critical/high issues to retry stages
    retry_stages: list[AnalysisStage] = []
    if has_critical:
        status = ValidationStatus.FAILED
        can_proceed = False
        for issue in validated_issues:
            if issue.severity in {ValidationSeverity.CRITICAL, ValidationSeverity.HIGH}:
                for stage in issue.affected_stages:
                    if stage in allowed_stages and stage not in retry_stages:
                        retry_stages.append(stage)
    elif insufficient_research:
        status = ValidationStatus.INSUFFICIENT_EVIDENCE
        can_proceed = True
    elif has_high or validated_issues:
        status = ValidationStatus.PASSED_WITH_WARNINGS
        can_proceed = True
    else:
        status = ValidationStatus.PASSED
        can_proceed = True

    return ValidationAnalysis(
        status=status,
        executive_assessment=draft.executive_assessment,
        issues=validated_issues,
        can_proceed=can_proceed,
        retry_stages=retry_stages,
        limitations=limitations,
    )
