from datetime import datetime, timezone
import pytest

from app.research.customer_evidence import (
    CustomerAnalysisDraft,
    CustomerEvidenceVerificationError,
    finalize_customer_analysis,
)
from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    CustomerFinding,
    CustomerFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchResult,
)


def _build_customer_ledger(
    stage: AnalysisStage = AnalysisStage.CUSTOMER_INTELLIGENCE,
) -> ResearchEvidenceLedger:
    ledger = ResearchEvidenceLedger(stage=stage)

    ledger.record_web_search_result(
        WebSearchResult(
            query="egypt gym membership retention",
            items=[
                WebSearchItem(
                    source_id="web_retention_1",
                    title="Egypt Fitness Report",
                    url="https://fitness.example/report",
                    snippet="62% of surveyed gym operators report retention friction.",
                ),
                WebSearchItem(
                    source_id="web_alternatives_2",
                    title="Manual Workarounds Survey",
                    url="https://workarounds.example/survey",
                    snippet="Small gym owners primarily track payments using Excel and WhatsApp.",
                ),
            ],
        ),
        retrieved_at=datetime(2026, 8, 24, 20, 0, tzinfo=timezone.utc),
    )

    return ledger


def test_finalizes_valid_customer_analysis():
    ledger = _build_customer_ledger()

    draft = CustomerAnalysisDraft(
        summary="Target customers rely on spreadsheets and face retention challenges.",
        findings=[
            CustomerFinding(
                statement="62% of independent gym operators report retention as a top challenge.",
                category=CustomerFindingCategory.PAIN_POINT,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=["web_retention_1"],
                is_numerical=True,
            ),
            CustomerFinding(
                statement="Small gym owners primarily use spreadsheets and WhatsApp for membership tracking.",
                category=CustomerFindingCategory.ALTERNATIVE,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.85,
                evidence_source_ids=["web_alternatives_2"],
                is_numerical=False,
            ),
            CustomerFinding(
                statement="A solution prioritizing renewal alerts may address administrative friction.",
                category=CustomerFindingCategory.VALUE_PROPOSITION,
                claim_kind=ResearchClaimKind.INFERRED,
                confidence=0.6,
                evidence_source_ids=["web_retention_1"],
                is_numerical=False,
            ),
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=["No direct willingness-to-pay evidence was found."],
    )

    result = finalize_customer_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.summary == draft.summary
    assert len(result.findings) == 3
    assert len(result.evidence_sources) == 2
    assert result.evidence_quality == ResearchEvidenceQuality.MODERATE
    assert result.evidence_sources[0].source_id == "web_retention_1"
    assert result.evidence_sources[0].title == "Egypt Fitness Report"


def test_rejects_hallucinated_source_id():
    ledger = _build_customer_ledger()

    draft = CustomerAnalysisDraft(
        summary="Customer summary.",
        findings=[
            CustomerFinding(
                statement="Fake observation.",
                category=CustomerFindingCategory.SEGMENT,
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.8,
                evidence_source_ids=["web_fake_999"],
                is_numerical=False,
            )
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(CustomerEvidenceVerificationError, match="not returned by a controlled"):
        finalize_customer_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_rejects_numerical_finding_without_evidence_id():
    ledger = _build_customer_ledger()

    draft = CustomerAnalysisDraft(
        summary="Customer summary.",
        findings=[
            CustomerFinding(
                statement="70% of gym owners experience friction.",
                category=CustomerFindingCategory.PAIN_POINT,
                claim_kind=ResearchClaimKind.INFERRED,
                confidence=0.5,
                evidence_source_ids=[],
                is_numerical=True,
            )
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(CustomerEvidenceVerificationError, match="Numerical Customer findings must"):
        finalize_customer_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_rejects_wrong_ledger_stage():
    market_ledger = ResearchEvidenceLedger(stage=AnalysisStage.MARKET_RESEARCH)

    draft = CustomerAnalysisDraft(
        summary="Draft.",
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Insufficient evidence."],
    )

    with pytest.raises(CustomerEvidenceVerificationError, match="CUSTOMER_INTELLIGENCE evidence ledger"):
        finalize_customer_analysis(
            draft=draft,
            evidence_ledger=market_ledger,
        )


def test_rejects_non_insufficient_analysis_without_sources():
    ledger = _build_customer_ledger()

    draft = CustomerAnalysisDraft(
        summary="Draft.",
        findings=[
            CustomerFinding(
                statement="Inferred segment preference.",
                category=CustomerFindingCategory.SEGMENT,
                claim_kind=ResearchClaimKind.INFERRED,
                confidence=0.5,
                evidence_source_ids=[],
                is_numerical=False,
            )
        ],
        evidence_quality=ResearchEvidenceQuality.MODERATE,
        limitations=[],
    )

    with pytest.raises(CustomerEvidenceVerificationError, match="must cite controlled evidence"):
        finalize_customer_analysis(
            draft=draft,
            evidence_ledger=ledger,
        )


def test_accepts_valid_insufficient_analysis():
    ledger = ResearchEvidenceLedger(stage=AnalysisStage.CUSTOMER_INTELLIGENCE)

    draft = CustomerAnalysisDraft(
        summary="No reliable customer evidence was found.",
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Bounded research window returned no relevant customer data."],
    )

    result = finalize_customer_analysis(
        draft=draft,
        evidence_ledger=ledger,
    )

    assert result.evidence_quality == ResearchEvidenceQuality.INSUFFICIENT
    assert len(result.findings) == 0
    assert len(result.evidence_sources) == 0
    assert result.limitations == draft.limitations
