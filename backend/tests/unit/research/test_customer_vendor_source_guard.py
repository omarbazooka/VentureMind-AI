from app.research.customer_evidence import (
    CustomerAnalysisDraft,
    VENDOR_SAFE_SUMMARY,
    VENDOR_SIDE_LIMITATION,
    finalize_customer_analysis,
)
from app.research.evidence import ResearchEvidenceLedger
from app.schemas.analysis import AnalysisStage
from app.schemas.research import (
    CustomerFinding,
    CustomerFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)
from app.schemas.tools import (
    PageRetrievalResult,
    WebSearchItem,
    WebSearchResult,
)


def _build_vendor_ledger() -> ResearchEvidenceLedger:
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="gym management software cairo",
            items=[
                WebSearchItem(
                    source_id="web_vendor_1",
                    title=(
                        "Gym Management Software in Cairo | "
                        "GymWyse - Starting at $59/mo"
                    ),
                    url=(
                        "https://gymwyse.fit/"
                        "gym-management-software-cairo"
                    ),
                    snippet=(
                        "GymWyse gives gym owners in Cairo "
                        "the tools to automate operations, "
                        "retain members, and grow revenue."
                    ),
                )
            ],
        )
    )

    ledger.record_page_retrieval_result(
        PageRetrievalResult(
            source_id="web_vendor_1",
            url=(
                "https://gymwyse.fit/"
                "gym-management-software-cairo"
            ),
            title=(
                "Gym Management Software in Cairo | "
                "GymWyse - Starting at $59/mo"
            ),
            content=(
                "GymWyse gives gym owners in Cairo "
                "the tools to automate operations, "
                "retain members, and grow revenue. "
                "Starting at $59/month."
            ),
        )
    )

    return ledger


def test_vendor_only_customer_claims_are_downgraded():
    ledger = _build_vendor_ledger()

    draft = CustomerAnalysisDraft(
        summary=(
            "Local cloud software options like GymWyse "
            "starting at $59/month indicate growing "
            "software adoption."
        ),
        findings=[
            CustomerFinding(
                statement=(
                    "Gym owners manually chase overdue "
                    "membership payments."
                ),
                category=CustomerFindingCategory.PAIN_POINT,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=["web_vendor_1"],
                is_numerical=False,
            ),
            CustomerFinding(
                statement=(
                    "The presence of localized platforms "
                    "indicates active market formation and "
                    "vendor belief in software adoption."
                ),
                category=CustomerFindingCategory.DEMAND_SIGNAL,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=["web_vendor_1"],
                is_numerical=False,
            ),
            CustomerFinding(
                statement=(
                    "Independent gyms rely on fragmented "
                    "manual tools and legacy software."
                ),
                category=CustomerFindingCategory.ALTERNATIVE,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.8,
                evidence_source_ids=["web_vendor_1"],
                is_numerical=False,
            ),
            CustomerFinding(
                statement=(
                    "Independent gym owners in Cairo are "
                    "targeted by this provider."
                ),
                category=CustomerFindingCategory.SEGMENT,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.8,
                evidence_source_ids=["web_vendor_1"],
                is_numerical=False,
            ),
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    result = finalize_customer_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    findings_by_category = {
        finding.category: finding
        for finding in result.findings
    }

    for category in (
        CustomerFindingCategory.PAIN_POINT,
        CustomerFindingCategory.ALTERNATIVE,
        CustomerFindingCategory.DEMAND_SIGNAL,
    ):
        finding = findings_by_category[category]
        assert finding.claim_kind == ResearchClaimKind.INFERRED
        assert finding.confidence <= 0.6

    assert (
        findings_by_category[
            CustomerFindingCategory.SEGMENT
        ].claim_kind
        == ResearchClaimKind.OBSERVED
    )

    assert result.evidence_quality == ResearchEvidenceQuality.WEAK
    assert result.summary == VENDOR_SAFE_SUMMARY
    assert VENDOR_SIDE_LIMITATION in result.limitations


def test_direct_customer_survey_stays_observed():
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="egypt gym owner survey",
            items=[
                WebSearchItem(
                    source_id="web_survey_1",
                    title="Egypt Gym Owner Survey",
                    url="https://research.example/survey",
                    snippet=(
                        "62% of surveyed gym operators "
                        "report retention friction."
                    ),
                )
            ],
        )
    )

    ledger.record_page_retrieval_result(
        PageRetrievalResult(
            source_id="web_survey_1",
            url="https://research.example/survey",
            title="Egypt Gym Owner Survey",
            content=(
                "62% of surveyed gym operators "
                "report retention friction."
            ),
        )
    )

    draft = CustomerAnalysisDraft(
        summary="Surveyed operators report retention friction.",
        findings=[
            CustomerFinding(
                statement=(
                    "62% of surveyed gym operators "
                    "report retention friction."
                ),
                category=CustomerFindingCategory.PAIN_POINT,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=["web_survey_1"],
                is_numerical=True,
            )
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    result = finalize_customer_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.findings[0].claim_kind == ResearchClaimKind.OBSERVED
    assert result.findings[0].confidence == 0.9
    assert result.evidence_quality == ResearchEvidenceQuality.MODERATE
    assert VENDOR_SIDE_LIMITATION not in result.limitations
