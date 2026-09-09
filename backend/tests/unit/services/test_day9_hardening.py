from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.schemas.finance import FinancialMetricName
from app.schemas.validation import (
    ValidationAnalysis,
    ValidationDraft,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStatus,
)
from app.schemas.validation_runtime import ValidationAnalysisContext
from app.services.decision_grounding import (
    DecisionGroundingError,
    validate_grounded_decision,
    validate_persisted_decision,
)
from app.services.validation_grounding import (
    ValidationGroundingError,
    validate_grounded_validation_analysis,
    validate_persisted_validation_analysis,
)


def _research_stage_ids():
    return {
        AnalysisStage.MARKET_RESEARCH: uuid4(),
        AnalysisStage.COMPETITOR_INTELLIGENCE: uuid4(),
        AnalysisStage.CUSTOMER_INTELLIGENCE: uuid4(),
    }


def _validation_context() -> ValidationAnalysisContext:
    finance_stage_id = uuid4()
    return ValidationAnalysisContext.model_construct(
        profile_snapshot=SimpleNamespace(profile_data={"problem": "Pain"}),
        research_gate=SimpleNamespace(
            can_proceed=True,
            insufficient_stages=[],
        ),
        research_stage_run_ids=_research_stage_ids(),
        market_analysis=SimpleNamespace(
            evidence_sources=[SimpleNamespace(source_id="src-market-1")]
        ),
        competitor_analysis=None,
        customer_analysis=None,
        business_strategy_stage_run_id=uuid4(),
        business_strategy=object(),
        finance_stage_run_id=finance_stage_id,
        finance_bundle=SimpleNamespace(
            base=SimpleNamespace(
                metrics=[SimpleNamespace(metric_name=FinancialMetricName.OPERATING_RESULT)]
            ),
            upside=SimpleNamespace(metrics=[]),
            downside=SimpleNamespace(metrics=[]),
        ),
        analytics_stage_run_id=uuid4(),
        decision_analytics=SimpleNamespace(
            finance_stage_run_id=finance_stage_id,
            kpis=[SimpleNamespace(metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT)],
            sensitivity=None,
        ),
        risk_stage_run_id=uuid4(),
        risk_analysis=SimpleNamespace(
            risks=[SimpleNamespace(title="Acquisition risk")]
        ),
    )


def _grounded_validation(context: ValidationAnalysisContext) -> ValidationAnalysis:
    return validate_grounded_validation_analysis(
        draft=ValidationDraft(
            executive_assessment="The analysis is usable with one bounded warning.",
            issues=[
                ValidationIssue(
                    category=ValidationIssueCategory.UNSUPPORTED_CLAIM,
                    severity=ValidationSeverity.LOW,
                    description="The conclusion needs explicit problem-field grounding.",
                    affected_stages=[AnalysisStage.BUSINESS_STRATEGY],
                    profile_fields=["problem"],
                )
            ],
        ),
        context=context,
    )


def test_validation_rejects_hallucinated_concrete_lineage():
    context = _validation_context()
    draft = ValidationDraft(
        executive_assessment="A source reference is not part of the accepted packet.",
        issues=[
            ValidationIssue(
                category=ValidationIssueCategory.UNSUPPORTED_CLAIM,
                severity=ValidationSeverity.MEDIUM,
                description="The cited source does not exist in the research packet.",
                affected_stages=[AnalysisStage.MARKET_RESEARCH],
                evidence_ids=["fake-source"],
            )
        ],
    )

    with pytest.raises(ValidationGroundingError, match="non-existent evidence ID"):
        validate_grounded_validation_analysis(draft=draft, context=context)


def test_validation_persistence_rejects_changed_upstream_stage_lineage():
    context = _validation_context()
    analysis = _grounded_validation(context)
    changed = context.model_copy(
        update={"finance_stage_run_id": uuid4()}
    )

    with pytest.raises(ValidationGroundingError, match="lineage changed"):
        validate_persisted_validation_analysis(
            analysis=analysis,
            context=changed,
        )


def _committee_context(
    *,
    validation_status: ValidationStatus = ValidationStatus.PASSED_WITH_WARNINGS,
) -> InvestmentCommitteeContext:
    validation_context = _validation_context()
    validation = _grounded_validation(validation_context)
    if validation_status != validation.status:
        validation = validation.model_copy(
            update={
                "status": validation_status,
                "can_proceed": validation_status != ValidationStatus.FAILED,
            }
        )

    return InvestmentCommitteeContext.model_construct(
        profile_snapshot=validation_context.profile_snapshot,
        research_gate=validation_context.research_gate,
        research_stage_run_ids=validation_context.research_stage_run_ids,
        market_analysis=validation_context.market_analysis,
        competitor_analysis=None,
        customer_analysis=None,
        business_strategy_stage_run_id=validation_context.business_strategy_stage_run_id,
        business_strategy=object(),
        finance_stage_run_id=validation_context.finance_stage_run_id,
        finance_bundle=validation_context.finance_bundle,
        analytics_stage_run_id=validation_context.analytics_stage_run_id,
        decision_analytics=validation_context.decision_analytics,
        risk_stage_run_id=validation_context.risk_stage_run_id,
        risk_analysis=validation_context.risk_analysis,
        validation_stage_run_id=uuid4(),
        validation_analysis=validation,
    )


def test_final_decision_rejects_hallucinated_lineage():
    context = _committee_context()
    draft = FinalDecisionDraft(
        decision=VentureDecision.CONDITIONAL_GO,
        confidence=DecisionConfidence.MEDIUM,
        rationale="The venture can proceed only under explicit validation conditions.",
        supporting_evidence_lineage=[
            {
                "kind": "EVIDENCE_SOURCE",
                "value": "fake-source",
                "stage": "MARKET_RESEARCH",
            }
        ],
    )

    with pytest.raises(DecisionGroundingError, match="unknown evidence source"):
        validate_grounded_decision(draft=draft, context=context)


def test_final_decision_caps_high_confidence_when_validation_warned():
    context = _committee_context()
    draft = FinalDecisionDraft(
        decision=VentureDecision.GO,
        confidence=DecisionConfidence.HIGH,
        rationale="The opportunity is attractive but the validator recorded a warning.",
        supporting_evidence_lineage=[
            {
                "kind": "PROFILE_FIELD",
                "value": "problem",
                "stage": None,
            }
        ],
    )

    result = validate_grounded_decision(draft=draft, context=context)

    assert result.confidence == DecisionConfidence.MEDIUM
    assert result.upstream_stage_run_ids


def test_final_decision_persistence_rejects_changed_validation_stage():
    context = _committee_context()
    result = validate_grounded_decision(
        draft=FinalDecisionDraft(
            decision=VentureDecision.CONDITIONAL_GO,
            confidence=DecisionConfidence.MEDIUM,
            rationale="Proceed only while the validated assumptions remain true.",
            supporting_evidence_lineage=[
                {
                    "kind": "PROFILE_FIELD",
                    "value": "problem",
                    "stage": None,
                }
            ],
        ),
        context=context,
    )
    changed = context.model_copy(
        update={"validation_stage_run_id": uuid4()}
    )

    with pytest.raises(DecisionGroundingError, match="lineage changed"):
        validate_persisted_decision(
            analysis=result,
            context=changed,
        )
