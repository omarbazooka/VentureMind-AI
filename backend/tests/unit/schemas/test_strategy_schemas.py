import pytest
from pydantic import ValidationError

from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategicClaimKind,
    StrategicInsight,
    StrategyStageClaim,
)

from app.schemas.analysis import AnalysisStage
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategicClaimKind,
    StrategicInsight,
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