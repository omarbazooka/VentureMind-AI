from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionAnalysis,
    FinalDecisionDraft,
    VentureDecision,
)


def test_decision_schemas_valid():
    draft = FinalDecisionDraft(
        decision=VentureDecision.CONDITIONAL_GO,
        confidence=DecisionConfidence.MEDIUM,
        rationale="Strong market demand verified by initial customer pain points, but break-even depends strictly on conservative fixed costs.",
        supporting_evidence_lineage=["src-market-1", "FINANCE"],
        strongest_positive_signals=["High customer willingness to switch", "Growing SAM"],
        strongest_negative_signals=["High initial CAC"],
        critical_assumptions=["Fixed cost stays under 20k/mo"],
        limitations=["Early stage survey data only"],
        what_could_change=["Lower than expected initial conversion"],
        recommended_next_steps=["Run pilot test with 10 B2B users"],
    )
    assert draft.decision == VentureDecision.CONDITIONAL_GO
    assert draft.confidence == DecisionConfidence.MEDIUM

    analysis = FinalDecisionAnalysis.model_validate(draft.model_dump())
    assert analysis.decision == VentureDecision.CONDITIONAL_GO
