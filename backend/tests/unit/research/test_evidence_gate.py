import pytest
from app.research.evidence_gate import (
    ResearchEvidenceGateInputError,
    ResearchEvidenceGateNotReadyError,
    evaluate_research_evidence_gate,
)
from app.schemas.analysis import AnalysisStage, AnalysisStageStatus
from app.schemas.research import (
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchGateIssueCode,
    ResearchStageGateInput,
)


def item(stage, quality=None, *, attempt=1, status=AnalysisStageStatus.COMPLETED, limitations=None):
    return ResearchStageGateInput(
        stage=stage,
        attempt=attempt,
        stage_status=status,
        evidence_quality=quality,
        limitations=limitations or [],
    )


def baseline(customer_quality=ResearchEvidenceQuality.MODERATE):
    return [
        item(AnalysisStage.MARKET_RESEARCH, ResearchEvidenceQuality.STRONG),
        item(AnalysisStage.COMPETITOR_INTELLIGENCE, ResearchEvidenceQuality.MODERATE),
        item(AnalysisStage.CUSTOMER_INTELLIGENCE, customer_quality),
    ]


def test_accepts_strong_and_moderate_research():
    result = evaluate_research_evidence_gate(stages=baseline())
    assert result.decision == ResearchGateDecision.ACCEPT
    assert result.can_proceed is True
    assert result.retry_stages == []
    assert result.insufficient_stages == []


def test_retryable_weak_stage_blocks_progress_even_with_non_retryable_gap():
    stages = baseline(customer_quality=ResearchEvidenceQuality.INSUFFICIENT)
    stages[0] = item(AnalysisStage.MARKET_RESEARCH, ResearchEvidenceQuality.WEAK)
    stages[2].limitations = ["Primary customer evidence is unavailable."]
    result = evaluate_research_evidence_gate(stages=stages)
    assert result.decision == ResearchGateDecision.RETRY
    assert result.can_proceed is False
    assert result.retry_stages == [AnalysisStage.MARKET_RESEARCH]
    assert result.insufficient_stages == [AnalysisStage.CUSTOMER_INTELLIGENCE]


def test_insufficient_gap_can_proceed_when_no_retryable_work_remains():
    stages = baseline(customer_quality=ResearchEvidenceQuality.INSUFFICIENT)
    stages[2].limitations = ["Requires interviews."]
    result = evaluate_research_evidence_gate(stages=stages)
    assert result.decision == ResearchGateDecision.INSUFFICIENT
    assert result.can_proceed is True
    assert result.insufficient_stages == [AnalysisStage.CUSTOMER_INTELLIGENCE]


def test_exhausted_weak_stage_becomes_insufficient_gap():
    stages = baseline()
    stages[1] = item(
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        ResearchEvidenceQuality.WEAK,
        attempt=2,
    )
    result = evaluate_research_evidence_gate(stages=stages)
    assert result.decision == ResearchGateDecision.INSUFFICIENT
    assessment = result.assessments[1]
    assert ResearchGateIssueCode.RETRY_EXHAUSTED in assessment.issue_codes
    assert assessment.retry_eligible is False


def test_failed_stage_is_retried_once():
    stages = baseline()
    stages[1] = item(
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        status=AnalysisStageStatus.FAILED,
    )
    result = evaluate_research_evidence_gate(stages=stages)
    assert result.decision == ResearchGateDecision.RETRY
    assert result.retry_stages == [AnalysisStage.COMPETITOR_INTELLIGENCE]


def test_pending_stage_means_gate_not_ready():
    stages = baseline()
    stages[0] = item(
        AnalysisStage.MARKET_RESEARCH,
        status=AnalysisStageStatus.PENDING,
    )
    with pytest.raises(ResearchEvidenceGateNotReadyError):
        evaluate_research_evidence_gate(stages=stages)


def test_missing_stage_is_rejected():
    with pytest.raises(ResearchEvidenceGateInputError):
        evaluate_research_evidence_gate(stages=baseline()[:2])
