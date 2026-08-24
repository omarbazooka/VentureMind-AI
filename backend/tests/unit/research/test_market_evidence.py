from datetime import (
    datetime,
    timezone,
)

import pytest

from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.research.market_evidence import (
    MarketAnalysisDraft,
    MarketEvidenceVerificationError,
    finalize_market_analysis,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    MarketFinding,
    MarketFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchResult,
)


def make_ledger_with_source(
) -> ResearchEvidenceLedger:
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="gym software Egypt",
            items=[
                WebSearchItem(
                    source_id="web_real",
                    title="Real source title",
                    url=(
                        "https://real-source.example/"
                        "egypt-gym-market"
                    ),
                    snippet=(
                        "Real provider evidence."
                    ),
                )
            ],
        ),
        retrieved_at=datetime(
            2026,
            8,
            24,
            20,
            0,
            tzinfo=timezone.utc,
        ),
    )

    return ledger


def test_finalizer_builds_canonical_sources_from_ledger():
    ledger = make_ledger_with_source()

    draft = MarketAnalysisDraft(
        summary="The target market shows demand.",
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory
                    .DEMAND_SIGNAL
                ),
                statement=(
                    "A documented demand signal exists."
                ),
                claim_kind=(
                    ResearchClaimKind.OBSERVED
                ),
                confidence=0.8,
                evidence_source_ids=[
                    "web_real"
                ],
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.MODERATE
        ),
        limitations=[
            "Only one source was used."
        ],
    )

    result = finalize_market_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert len(result.evidence_sources) == 1

    source = result.evidence_sources[0]

    assert source.source_id == "web_real"
    assert source.title == "Real source title"
    assert (
        str(source.url)
        == (
            "https://real-source.example/"
            "egypt-gym-market"
        )
    )
    assert (
        source.excerpt
        == "Real provider evidence."
    )
    assert source.retrieved_at is not None


def test_finalizer_rejects_hallucinated_source_id():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    draft = MarketAnalysisDraft(
        summary="Claimed market evidence.",
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory.TREND
                ),
                statement="A trend exists.",
                claim_kind=(
                    ResearchClaimKind.OBSERVED
                ),
                confidence=0.8,
                evidence_source_ids=[
                    "web_hallucinated"
                ],
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.MODERATE
        ),
        limitations=[],
    )

    with pytest.raises(
        MarketEvidenceVerificationError
    ):
        finalize_market_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_non_insufficient_without_sources():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    draft = MarketAnalysisDraft(
        summary="An inferred market view.",
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory.TREND
                ),
                statement=(
                    "Adoption may increase."
                ),
                claim_kind=(
                    ResearchClaimKind.INFERRED
                ),
                confidence=0.4,
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.WEAK
        ),
        limitations=[
            "The statement is inferred."
        ],
    )

    with pytest.raises(
        MarketEvidenceVerificationError
    ):
        finalize_market_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_numerical_finding_without_source():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    draft = MarketAnalysisDraft(
        summary="An unsupported numerical estimate.",
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory
                    .MARKET_SIZE
                ),
                statement="The market may grow 20%.",
                claim_kind=(
                    ResearchClaimKind.INFERRED
                ),
                confidence=0.4,
                is_numerical=True,
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.INSUFFICIENT
        ),
        limitations=[
            "No supporting source was available."
        ],
    )

    with pytest.raises(
        MarketEvidenceVerificationError
    ):
        finalize_market_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_accepts_insufficient_without_findings():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    draft = MarketAnalysisDraft(
        summary="Reliable evidence was unavailable.",
        findings=[],
        evidence_quality=(
            ResearchEvidenceQuality.INSUFFICIENT
        ),
        limitations=[
            "No reliable sources were found."
        ],
    )

    result = finalize_market_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.findings == []
    assert result.evidence_sources == []
    assert (
        result.evidence_quality
        == ResearchEvidenceQuality.INSUFFICIENT
    )
