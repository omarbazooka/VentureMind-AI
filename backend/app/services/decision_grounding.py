from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionAnalysis,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.schemas.validation import ValidationStatus


class DecisionGroundingError(ValueError):
    pass


def validate_grounded_decision(
    *,
    draft: FinalDecisionDraft,
    context: InvestmentCommitteeContext,
) -> FinalDecisionAnalysis:
    insufficient_research = bool(context.research_gate.insufficient_stages)
    validation_status = context.validation_analysis.status

    # Rule: Confidence cannot be HIGH if evidence was insufficient or validation flagged issues
    confidence = draft.confidence
    if (insufficient_research or validation_status == ValidationStatus.INSUFFICIENT_EVIDENCE) and confidence == DecisionConfidence.HIGH:
        confidence = DecisionConfidence.MEDIUM

    decision = draft.decision
    if validation_status == ValidationStatus.FAILED and decision == VentureDecision.GO:
        raise DecisionGroundingError(
            "Cannot issue a GO decision when Independent Validation has FAILED"
        )

    if insufficient_research and decision == VentureDecision.GO:
        # If research was fundamentally insufficient, GO must be at most CONDITIONAL_GO
        decision = VentureDecision.CONDITIONAL_GO

    limitations = list(draft.limitations)
    if insufficient_research:
        limitations.append(
            "Final decision is bounded by insufficient research evidence in upstream stages."
        )

    return FinalDecisionAnalysis(
        decision=decision,
        confidence=confidence,
        rationale=draft.rationale,
        supporting_evidence_lineage=draft.supporting_evidence_lineage,
        strongest_positive_signals=draft.strongest_positive_signals,
        strongest_negative_signals=draft.strongest_negative_signals,
        critical_assumptions=draft.critical_assumptions,
        limitations=limitations,
        what_could_change=draft.what_could_change,
        recommended_next_steps=draft.recommended_next_steps,
    )
