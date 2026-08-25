from datetime import (
    datetime,
    timezone,
)

import pytest

from app.research.competitor_evidence import (
    CompetitorAnalysisDraft,
    CompetitorEvidenceVerificationError,
    finalize_competitor_analysis,
)
from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    CompetitorFinding,
    CompetitorFindingCategory,
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
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query=(
                "gym management software "
                "competitors Egypt"
            ),
            items=[
                WebSearchItem(
                    source_id="web_real",
                    title=(
                        "Real Competitor "
                        "Product Page"
                    ),
                    url=(
                        "https://"
                        "competitor.example/"
                        "pricing"
                    ),
                    snippet=(
                        "The provider returned "
                        "competitor pricing "
                        "evidence."
                    ),
                )
            ],
        ),
        retrieved_at=datetime(
            2026,
            8,
            25,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    return ledger


def make_ledger_after_empty_search(
) -> ResearchEvidenceLedger:
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query=(
                "independent gym management "
                "software competitors Egypt"
            ),
            items=[],
        ),
        retrieved_at=datetime(
            2026,
            8,
            25,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    return ledger


def test_finalizer_builds_canonical_sources_from_ledger():
    ledger = make_ledger_with_source()

    draft = CompetitorAnalysisDraft(
        summary=(
            "A relevant competitor "
            "was identified."
        ),
        findings=[
            CompetitorFinding(
                category=(
                    CompetitorFindingCategory
                    .PRICING
                ),
                statement=(
                    "The competitor publishes "
                    "pricing on its website."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .OBSERVED
                ),
                confidence=0.9,
                evidence_source_ids=[
                    "web_real"
                ],
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.MODERATE
        ),
        limitations=[
            "Only one competitor source "
            "was used."
        ],
    )

    result = (
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )
    )

    assert (
        len(result.evidence_sources)
        == 1
    )

    source = result.evidence_sources[0]

    assert (
        source.source_id
        == "web_real"
    )

    assert (
        source.title
        == "Real Competitor Product Page"
    )

    assert (
        str(source.url)
        == (
            "https://"
            "competitor.example/pricing"
        )
    )

    assert (
        source.excerpt
        == (
            "The provider returned "
            "competitor pricing evidence."
        )
    )

    assert source.retrieved_at is not None


def test_finalizer_rejects_hallucinated_source_id():
    ledger = make_ledger_after_empty_search()

    draft = CompetitorAnalysisDraft(
        summary=(
            "A competitor was allegedly "
            "identified."
        ),
        findings=[
            CompetitorFinding(
                category=(
                    CompetitorFindingCategory
                    .COMPETITOR
                ),
                statement=(
                    "A competitor exists."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .OBSERVED
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
        CompetitorEvidenceVerificationError
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_non_insufficient_without_sources():
    ledger = make_ledger_after_empty_search()

    draft = CompetitorAnalysisDraft(
        summary=(
            "An inferred competitor view."
        ),
        findings=[
            CompetitorFinding(
                category=(
                    CompetitorFindingCategory
                    .WHITESPACE
                ),
                statement=(
                    "Local operators may "
                    "prefer simpler software."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .INFERRED
                ),
                confidence=0.4,
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality.WEAK
        ),
        limitations=[
            "The whitespace conclusion "
            "is inferred."
        ],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_numerical_pricing_without_source():
    ledger = make_ledger_after_empty_search()

    draft = CompetitorAnalysisDraft(
        summary=(
            "Unsupported competitor pricing."
        ),
        findings=[
            CompetitorFinding(
                category=(
                    CompetitorFindingCategory
                    .PRICING
                ),
                statement=(
                    "A competitor may charge "
                    "$50 per month."
                ),
                claim_kind=(
                    ResearchClaimKind.INFERRED
                ),
                confidence=0.4,
                is_numerical=True,
            )
        ],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "No pricing source "
            "was available."
        ],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_accepts_insufficient_after_empty_search():
    ledger = make_ledger_after_empty_search()

    draft = CompetitorAnalysisDraft(
        summary=(
            "Reliable competitor evidence "
            "was unavailable."
        ),
        findings=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "The controlled search did not "
            "return reliable competitor "
            "evidence."
        ],
    )

    result = (
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )
    )

    assert result.findings == []

    assert (
        result.evidence_sources
        == []
    )

    assert (
        result.evidence_quality
        == (
            ResearchEvidenceQuality
            .INSUFFICIENT
        )
    )

    assert len(
        ledger.search_queries
    ) == 1


def test_finalizer_rejects_when_no_controlled_search_was_attempted():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    draft = CompetitorAnalysisDraft(
        summary=(
            "No competitor evidence "
            "was available."
        ),
        findings=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "No evidence was available."
        ],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match=(
            "must attempt controlled "
            "research"
        ),
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_wrong_stage_ledger():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    draft = CompetitorAnalysisDraft(
        summary=(
            "Reliable competitor evidence "
            "was unavailable."
        ),
        findings=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "No competitor evidence."
        ],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )
