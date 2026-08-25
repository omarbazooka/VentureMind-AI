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
    CompetitorDetail,
    CompetitorProfile,
    CompetitorRelationship,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)
from app.schemas.tools import (
    PageRetrievalResult,
    WebSearchItem,
    WebSearchResult,
)


RETRIEVED_AT = datetime(
    2026,
    8,
    25,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_ledger_with_detail_source(
) -> ResearchEvidenceLedger:
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="gym management software Egypt",
            items=[
                WebSearchItem(
                    source_id="web_real",
                    title="Competitor Search Result",
                    url="https://competitor.example/pricing",
                    snippet="Official competitor result.",
                )
            ],
        ),
        retrieved_at=RETRIEVED_AT,
    )

    ledger.record_page_retrieval_result(
        PageRetrievalResult(
            source_id="web_real",
            url="https://competitor.example/pricing",
            title="Competitor Pricing",
            content=(
                "Gym management software with "
                "memberships and scheduling. "
                "Starter pricing is $99/month."
            ),
        ),
        retrieved_at=RETRIEVED_AT,
    )

    return ledger


def make_profile(
    *,
    source_id: str = "web_real",
) -> CompetitorProfile:
    return CompetitorProfile(
        name="Competitor One",
        relationship=CompetitorRelationship.DIRECT,
        relevance_summary=(
            "Serves gyms with overlapping "
            "membership and scheduling workflows."
        ),
        confidence=0.9,
        primary_source_id=source_id,
        strengths=[
            CompetitorDetail(
                statement=(
                    "Combines membership management "
                    "and scheduling in one product."
                ),
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=[source_id],
            )
        ],
        weaknesses=[
            CompetitorDetail(
                statement=(
                    "The published positioning suggests "
                    "a broader product scope that may "
                    "increase setup complexity for very "
                    "small gyms."
                ),
                claim_kind=ResearchClaimKind.INFERRED,
                confidence=0.45,
                evidence_source_ids=[source_id],
            )
        ],
        pricing=CompetitorDetail(
            statement="Starter pricing is $99/month.",
            claim_kind=ResearchClaimKind.OBSERVED,
            confidence=0.95,
            evidence_source_ids=[source_id],
            is_numerical=True,
        ),
    )


def test_finalizer_builds_frontend_ready_profiles_without_redundant_findings():
    ledger = make_ledger_with_detail_source()

    draft = CompetitorAnalysisDraft(
        summary="A direct competitor was verified.",
        competitors=[make_profile()],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.STRONG,
        limitations=[],
    )

    result = finalize_competitor_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert len(result.competitors) == 1
    assert result.findings == []
    assert result.competitors[0].name == "Competitor One"
    assert (
        result.competitors[0].pricing.statement
        == "Starter pricing is $99/month."
    )
    assert len(result.evidence_sources) == 1
    assert result.evidence_sources[0].source_id == "web_real"
    assert result.evidence_sources[0].title == "Competitor Pricing"
    assert "$99/month" in result.evidence_sources[0].excerpt


def test_finalizer_rejects_hallucinated_profile_source_id():
    ledger = make_ledger_with_detail_source()

    draft = CompetitorAnalysisDraft(
        summary="A claimed competitor exists.",
        competitors=[
            make_profile(
                source_id="web_hallucinated"
            )
        ],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="not returned by a controlled",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_non_insufficient_without_page_retrieval():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="gym software Egypt",
            items=[
                WebSearchItem(
                    source_id="web_real",
                    title="Search source",
                    url="https://competitor.example",
                    snippet="Competitor evidence.",
                )
            ],
        ),
        retrieved_at=RETRIEVED_AT,
    )

    draft = CompetitorAnalysisDraft(
        summary="A competitor was identified.",
        competitors=[make_profile()],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="page retrieval",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_when_no_controlled_search_was_attempted():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    draft = CompetitorAnalysisDraft(
        summary="No competitor evidence was available.",
        competitors=[],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["No evidence was available."],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="must attempt controlled research",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_accepts_insufficient_after_empty_search():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="niche competitor search",
            items=[],
        ),
        retrieved_at=RETRIEVED_AT,
    )

    draft = CompetitorAnalysisDraft(
        summary="Reliable competitor evidence was unavailable.",
        competitors=[],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=[
            "The controlled search returned no "
            "reliable competitor evidence."
        ],
    )

    result = finalize_competitor_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.competitors == []
    assert result.findings == []
    assert result.evidence_sources == []
    assert (
        result.evidence_quality
        == ResearchEvidenceQuality.INSUFFICIENT
    )


def test_competitor_detail_rejects_numerical_pricing_without_source():
    with pytest.raises(
        ValueError,
        match="Numerical competitor details",
    ):
        CompetitorDetail(
            statement="Pricing may be $50/month.",
            claim_kind=ResearchClaimKind.INFERRED,
            confidence=0.4,
            is_numerical=True,
        )


def test_finalizer_rejects_wrong_stage_ledger():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    draft = CompetitorAnalysisDraft(
        summary="Reliable competitor evidence was unavailable.",
        competitors=[],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["No competitor evidence."],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="COMPETITOR_INTELLIGENCE",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_rejects_inferred_missing_feature_weakness():
    ledger = make_ledger_with_detail_source()

    profile = make_profile()
    profile.weaknesses = [
        CompetitorDetail(
            statement="Lacks native Arabic receipt printing.",
            claim_kind=ResearchClaimKind.INFERRED,
            confidence=0.4,
            evidence_source_ids=["web_real"],
        )
    ]

    draft = CompetitorAnalysisDraft(
        summary="A competitor was identified.",
        competitors=[profile],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="unsupported absence assertions",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_accepts_valid_inferred_tradeoff_weakness():
    ledger = make_ledger_with_detail_source()

    profile = make_profile()
    profile.weaknesses = [
        CompetitorDetail(
            statement=(
                "The published positioning suggests a broader product scope "
                "that may increase setup complexity for very small gyms."
            ),
            claim_kind=ResearchClaimKind.INFERRED,
            confidence=0.45,
            evidence_source_ids=["web_real"],
        )
    ]

    draft = CompetitorAnalysisDraft(
        summary="A competitor was identified.",
        competitors=[profile],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    result = finalize_competitor_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert len(result.competitors) == 1
    assert (
        result.competitors[0].weaknesses[0].statement
        == "The published positioning suggests a broader product scope that may increase setup complexity for very small gyms."
    )


def test_finalizer_rejects_unknown_pricing_placeholder():
    ledger = make_ledger_with_detail_source()

    profile = make_profile()
    profile.pricing = CompetitorDetail(
        statement="Pricing is not published.",
        claim_kind=ResearchClaimKind.OBSERVED,
        confidence=0.9,
        evidence_source_ids=["web_real"],
    )

    draft = CompetitorAnalysisDraft(
        summary="A competitor was identified.",
        competitors=[profile],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(
        CompetitorEvidenceVerificationError,
        match="Unknown or unpublished pricing must be represented as pricing=None",
    ):
        finalize_competitor_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_finalizer_accepts_verified_real_pricing():
    ledger = make_ledger_with_detail_source()

    profile = make_profile()
    profile.pricing = CompetitorDetail(
        statement="Starter pricing is $99/month.",
        claim_kind=ResearchClaimKind.OBSERVED,
        confidence=0.95,
        evidence_source_ids=["web_real"],
        is_numerical=True,
    )

    draft = CompetitorAnalysisDraft(
        summary="A competitor was identified.",
        competitors=[profile],
        findings=[],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    result = finalize_competitor_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.competitors[0].pricing is not None
    assert (
        result.competitors[0].pricing.statement
        == "Starter pricing is $99/month."
    )
