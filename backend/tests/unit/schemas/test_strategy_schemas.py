import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategicClaimKind,
    StrategicInsight,
    StrategyStageClaim,
)

def test_research_inference_accepts_grounded_support():
    insight = StrategicInsight(
        statement=(
            "Simple onboarding may be a "
            "defensible positioning angle."
        ),
        claim_kind=(
            StrategicClaimKind
            .RESEARCH_INFERENCE
        ),
        confidence=0.78,
        supporting_stages=[
            AnalysisStage
            .CUSTOMER_INTELLIGENCE,
            AnalysisStage
            .COMPETITOR_INTELLIGENCE,
        ],
        evidence_source_ids=[
            "customer-source-1",
            "competitor-source-1",
        ],
    )

    assert (
        insight.claim_kind
        == StrategicClaimKind
        .RESEARCH_INFERENCE
    )

    assert (
        AnalysisStage
        .CUSTOMER_INTELLIGENCE
        in insight.supporting_stages
    )


def test_profile_fact_requires_profile_field():
    with pytest.raises(
        ValidationError
    ):
        StrategicInsight(
            statement=(
                "The venture targets Egypt."
            ),
            claim_kind=(
                StrategicClaimKind
                .PROFILE_FACT
            ),
            confidence=1.0,
        )


def test_profile_fact_accepts_profile_field_reference():
    insight = StrategicInsight(
        statement=(
            "The venture targets Egypt."
        ),
        claim_kind=(
            StrategicClaimKind
            .PROFILE_FACT
        ),
        confidence=1.0,
        profile_fields=[
            "target_geography"
        ],
    )

    assert insight.profile_fields == [
        "target_geography"
    ]


def test_research_inference_requires_supporting_stage():
    with pytest.raises(
        ValidationError
    ):
        StrategicInsight(
            statement=(
                "The market may reward "
                "simple onboarding."
            ),
            claim_kind=(
                StrategicClaimKind
                .RESEARCH_INFERENCE
            ),
            confidence=0.6,
        )


def test_strategy_cannot_support_itself():
    with pytest.raises(
        ValidationError
    ):
        StrategicInsight(
            statement=(
                "The strategy proves "
                "the strategy."
            ),
            claim_kind=(
                StrategicClaimKind
                .RESEARCH_INFERENCE
            ),
            confidence=0.5,
            supporting_stages=[
                AnalysisStage
                .BUSINESS_STRATEGY
            ],
        )


def test_ai_assumption_can_be_explicitly_unverified():
    insight = StrategicInsight(
        statement=(
            "Assume an initial "
            "self-service acquisition model."
        ),
        claim_kind=(
            StrategicClaimKind
            .AI_ASSUMPTION
        ),
        confidence=0.4,
    )

    assert (
        insight.evidence_source_ids
        == []
    )

    assert (
        insight.supporting_stages
        == []
    )


def test_business_strategy_analysis_accepts_structured_result():
    result = BusinessStrategyAnalysis(
        executive_summary=(
            "The venture has a plausible "
            "SME-focused positioning."
        ),
        positioning=[
            StrategicInsight(
                statement=(
                    "Focus initial positioning "
                    "on operational simplicity."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .RESEARCH_INFERENCE
                ),
                confidence=0.75,
                supporting_stages=[
                    AnalysisStage
                    .CUSTOMER_INTELLIGENCE
                ],
            )
        ],
        critical_assumptions=[
            StrategicInsight(
                statement=(
                    "Assume customers prefer "
                    "self-service onboarding."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .AI_ASSUMPTION
                ),
                confidence=0.4,
            )
        ],
        finance_questions=[
            "What is the expected selling price?",
            "What are the main variable costs?",
        ],
        limitations=[
            "Pricing has not yet been validated."
        ],
    )

    assert len(
        result.positioning
    ) == 1

    assert len(
        result.finance_questions
    ) == 2


def test_strategy_rejects_unknown_fields():
    with pytest.raises(
        ValidationError
    ):
        BusinessStrategyAnalysis(
            executive_summary=(
                "Strategy summary."
            ),
            invented_field="not allowed",
        )


def make_profile_snapshot() -> AnalysisProfileSnapshot:
    return AnalysisProfileSnapshot(
        readiness=(
            ProfileReadinessStatus
            .READY_FOR_ANALYSIS
        ),
        profile_data={
            "idea": "Example SaaS venture",
            "target_geography": "Egypt",
        },
    )


def make_gate_assessments(
    *,
    evidence_quality: ResearchEvidenceQuality,
) -> list[ResearchStageGateAssessment]:
    return [
        ResearchStageGateAssessment(
            stage=stage,
            attempt=1,
            stage_status=(
                AnalysisStageStatus.COMPLETED
            ),
            evidence_quality=evidence_quality,
        )
        for stage in (
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        )
    ]


def make_insufficient_gate(
    *,
    insufficient_stages: list[AnalysisStage],
) -> ResearchEvidenceGateResult:
    return ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision.INSUFFICIENT
        ),
        can_proceed=True,
        assessments=make_gate_assessments(
            evidence_quality=(
                ResearchEvidenceQuality
                .INSUFFICIENT
            ),
        ),
        insufficient_stages=(
            insufficient_stages
        ),
    )

def test_strategy_claim_requires_strategy_stage():
    with pytest.raises(
        ValidationError
    ):
        StrategyStageClaim(
            stage_run_id=(
                "11111111-1111-1111-1111-111111111111"
            ),
            analysis_run_id=(
                "22222222-2222-2222-2222-222222222222"
            ),
            stage=(
                AnalysisStage.MARKET_RESEARCH
            ),
            attempt=1,
            profile_snapshot=(
                make_profile_snapshot()
            ),
            research_gate=(
                make_insufficient_gate(
                    insufficient_stages=[
                        AnalysisStage.MARKET_RESEARCH,
                        AnalysisStage.COMPETITOR_INTELLIGENCE,
                        AnalysisStage.CUSTOMER_INTELLIGENCE,
                    ],
                )
            ),
        )


def test_strategy_claim_rejects_blocked_research_gate():
    gate = ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision.RETRY
        ),
        can_proceed=False,
        assessments=make_gate_assessments(
            evidence_quality=(
                ResearchEvidenceQuality.WEAK
            ),
        ),
        retry_stages=[
            AnalysisStage.MARKET_RESEARCH
        ],
    )

    with pytest.raises(
        ValidationError
    ):
        StrategyStageClaim(
            stage_run_id=(
                "11111111-1111-1111-1111-111111111111"
            ),
            analysis_run_id=(
                "22222222-2222-2222-2222-222222222222"
            ),
            stage=(
                AnalysisStage.BUSINESS_STRATEGY
            ),
            attempt=1,
            profile_snapshot=(
                make_profile_snapshot()
            ),
            research_gate=gate,
        )


def test_strategy_claim_allows_declared_insufficient_results():
    gate = make_insufficient_gate(
        insufficient_stages=[
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        ],
    )

    claim = StrategyStageClaim(
        stage_run_id=(
            "11111111-1111-1111-1111-111111111111"
        ),
        analysis_run_id=(
            "22222222-2222-2222-2222-222222222222"
        ),
        stage=(
            AnalysisStage.BUSINESS_STRATEGY
        ),
        attempt=1,
        profile_snapshot=(
            make_profile_snapshot()
        ),
        research_gate=gate,
    )

    assert claim.market_analysis is None
    assert claim.competitor_analysis is None
    assert claim.customer_analysis is None


def test_strategy_claim_rejects_undeclared_missing_result():
    gate = make_insufficient_gate(
        insufficient_stages=[
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        ],
    )

    with pytest.raises(
        ValidationError
    ):
        StrategyStageClaim(
            stage_run_id=(
                "11111111-1111-1111-1111-111111111111"
            ),
            analysis_run_id=(
                "22222222-2222-2222-2222-222222222222"
            ),
            stage=(
                AnalysisStage.BUSINESS_STRATEGY
            ),
            attempt=1,
            profile_snapshot=(
                make_profile_snapshot()
            ),
            research_gate=gate,

            # market_analysis intentionally missing
        )