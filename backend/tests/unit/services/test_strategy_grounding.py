from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    EvidenceProvenance,
    MarketAnalysis,
    MarketFinding,
    MarketFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategicClaimKind,
    StrategicInsight,
    StrategyStageClaim,
)
from app.services.strategy_grounding import (
    StrategyGroundingError,
    finalize_business_strategy,
)


def make_market_analysis() -> MarketAnalysis:
    return MarketAnalysis(
        summary=(
            "The market has a relevant "
            "demand signal."
        ),
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory
                    .DEMAND_SIGNAL
                ),
                statement=(
                    "A relevant demand "
                    "signal exists."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .OBSERVED
                ),
                confidence=0.8,
                evidence_source_ids=[
                    "market-source-1"
                ],
            )
        ],
        evidence_sources=[
            ResearchEvidenceSource(
                source_id=(
                    "market-source-1"
                ),
                provenance=(
                    EvidenceProvenance.WEB
                ),
                title=(
                    "Example market source"
                ),
                url=(
                    "https://example.com/"
                    "market"
                ),
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality
            .MODERATE
        ),
    )


def make_claim() -> StrategyStageClaim:
    return StrategyStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
        ),
        attempt=1,
        profile_snapshot=(
            AnalysisProfileSnapshot(
                readiness=(
                    ProfileReadinessStatus
                    .READY_FOR_ANALYSIS
                ),
                profile_data={
                    "idea_description": (
                        "Gym management SaaS"
                    ),
                    "target_country": (
                        "Egypt"
                    ),
                },
            )
        ),
        research_gate=(
            ResearchEvidenceGateResult(
                decision=(
                    ResearchGateDecision
                    .INSUFFICIENT
                ),
                can_proceed=True,
                assessments=[
                    ResearchStageGateAssessment(
                        stage=(
                            AnalysisStage
                            .MARKET_RESEARCH
                        ),
                        attempt=1,
                        stage_status=(
                            AnalysisStageStatus
                            .COMPLETED
                        ),
                        evidence_quality=(
                            ResearchEvidenceQuality
                            .MODERATE
                        ),
                    ),
                    ResearchStageGateAssessment(
                        stage=(
                            AnalysisStage
                            .COMPETITOR_INTELLIGENCE
                        ),
                        attempt=1,
                        stage_status=(
                            AnalysisStageStatus
                            .COMPLETED
                        ),
                        evidence_quality=(
                            ResearchEvidenceQuality
                            .INSUFFICIENT
                        ),
                    ),
                    ResearchStageGateAssessment(
                        stage=(
                            AnalysisStage
                            .CUSTOMER_INTELLIGENCE
                        ),
                        attempt=1,
                        stage_status=(
                            AnalysisStageStatus
                            .COMPLETED
                        ),
                        evidence_quality=(
                            ResearchEvidenceQuality
                            .INSUFFICIENT
                        ),
                    ),
                ],
                insufficient_stages=[
                    AnalysisStage
                    .COMPETITOR_INTELLIGENCE,
                    AnalysisStage
                    .CUSTOMER_INTELLIGENCE,
                ],
            )
        ),
        market_analysis=(
            make_market_analysis()
        ),
    )


def test_finalizer_accepts_grounded_strategy():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "The venture has a plausible "
            "initial direction."
        ),
        positioning=[
            StrategicInsight(
                statement=(
                    "The venture targets "
                    "Egypt."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .PROFILE_FACT
                ),
                confidence=1.0,
                profile_fields=[
                    "target_country"
                ],
            ),
            StrategicInsight(
                statement=(
                    "The market evidence "
                    "supports further testing."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .RESEARCH_INFERENCE
                ),
                confidence=0.7,
                supporting_stages=[
                    AnalysisStage
                    .MARKET_RESEARCH
                ],
                evidence_source_ids=[
                    "market-source-1"
                ],
            ),
        ],
        limitations=[
            "Competitor and customer "
            "evidence are insufficient."
        ],
    )

    result = finalize_business_strategy(
        analysis=analysis,
        claim=claim,
    )

    assert isinstance(
        result,
        BusinessStrategyAnalysis,
    )


def test_finalizer_rejects_unknown_profile_field():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "Strategy summary."
        ),
        positioning=[
            StrategicInsight(
                statement=(
                    "The venture has "
                    "validated revenue."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .PROFILE_FACT
                ),
                confidence=1.0,
                profile_fields=[
                    "validated_revenue"
                ],
            )
        ],
        limitations=[
            "Research is incomplete."
        ],
    )

    with pytest.raises(
        StrategyGroundingError
    ):
        finalize_business_strategy(
            analysis=analysis,
            claim=claim,
        )


def test_finalizer_rejects_unknown_evidence_source():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "Strategy summary."
        ),
        positioning=[
            StrategicInsight(
                statement=(
                    "The market supports "
                    "the strategy."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .RESEARCH_INFERENCE
                ),
                confidence=0.7,
                supporting_stages=[
                    AnalysisStage
                    .MARKET_RESEARCH
                ],
                evidence_source_ids=[
                    "invented-source"
                ],
            )
        ],
        limitations=[
            "Research is incomplete."
        ],
    )

    with pytest.raises(
        StrategyGroundingError
    ):
        finalize_business_strategy(
            analysis=analysis,
            claim=claim,
        )


def test_finalizer_rejects_missing_supporting_result():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "Strategy summary."
        ),
        positioning=[
            StrategicInsight(
                statement=(
                    "Customer research "
                    "supports this direction."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .RESEARCH_INFERENCE
                ),
                confidence=0.7,
                supporting_stages=[
                    AnalysisStage
                    .CUSTOMER_INTELLIGENCE
                ],
            )
        ],
        limitations=[
            "Customer evidence is "
            "insufficient."
        ],
    )

    with pytest.raises(
        StrategyGroundingError
    ):
        finalize_business_strategy(
            analysis=analysis,
            claim=claim,
        )


def test_finalizer_rejects_evidence_backed_ai_assumption():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "Strategy summary."
        ),
        critical_assumptions=[
            StrategicInsight(
                statement=(
                    "Assume market adoption "
                    "will accelerate."
                ),
                claim_kind=(
                    StrategicClaimKind
                    .AI_ASSUMPTION
                ),
                confidence=0.4,
                supporting_stages=[
                    AnalysisStage
                    .MARKET_RESEARCH
                ],
                evidence_source_ids=[
                    "market-source-1"
                ],
            )
        ],
        limitations=[
            "Research is incomplete."
        ],
    )

    with pytest.raises(
        StrategyGroundingError
    ):
        finalize_business_strategy(
            analysis=analysis,
            claim=claim,
        )


def test_finalizer_requires_limitations_for_insufficient_gate():
    claim = make_claim()

    analysis = BusinessStrategyAnalysis(
        executive_summary=(
            "Strategy summary."
        ),
    )

    with pytest.raises(
        StrategyGroundingError
    ):
        finalize_business_strategy(
            analysis=analysis,
            claim=claim,
        )