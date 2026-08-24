from datetime import (
    datetime,
    timezone,
)

import pytest

from app.research.evidence import (
    EvidenceSourceCollisionError,
    ResearchEvidenceLedger,
    ResearchEvidenceLedgerError,
    UnknownEvidenceSourceError,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchResult,
)


def make_result(
    *,
    source_id: str = "web_real_source",
    url: str = (
        "https://example.com/report"
    ),
) -> WebSearchResult:
    return WebSearchResult(
        query="gym software Egypt",
        items=[
            WebSearchItem(
                source_id=source_id,
                title="Real market report",
                url=url,
                snippet=(
                    "Evidence returned "
                    "by the provider."
                ),
            )
        ],
    )


def test_records_real_web_evidence():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    retrieved_at = datetime(
        2026,
        8,
        24,
        20,
        0,
        tzinfo=timezone.utc,
    )

    ledger.record_web_search_result(
        make_result(),
        retrieved_at=retrieved_at,
    )

    source = ledger.get_source(
        "web_real_source"
    )

    assert (
        source.source_id
        == "web_real_source"
    )

    assert (
        str(source.url)
        == (
            "https://example.com/"
            "report"
        )
    )

    assert (
        source.title
        == "Real market report"
    )

    assert (
        source.excerpt
        == (
            "Evidence returned "
            "by the provider."
        )
    )

    assert (
        source.retrieved_at
        == retrieved_at
    )

    assert ledger.search_queries == (
        "gym software Egypt",
    )


def test_repeated_same_source_is_idempotent():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    result = make_result()

    ledger.record_web_search_result(
        result
    )

    ledger.record_web_search_result(
        result
    )

    assert ledger.source_ids == (
        "web_real_source",
    )

    assert ledger.search_queries == (
        "gym software Egypt",
        "gym software Egypt",
    )


def test_rejects_source_id_url_collision():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    ledger.record_web_search_result(
        make_result(
            source_id="web_same_id",
            url=(
                "https://example.com/a"
            ),
        )
    )

    with pytest.raises(
        EvidenceSourceCollisionError
    ):
        ledger.record_web_search_result(
            make_result(
                source_id="web_same_id",
                url=(
                    "https://example.com/b"
                ),
            )
        )


def test_rejects_unknown_source_id():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    with pytest.raises(
        UnknownEvidenceSourceError
    ):
        ledger.get_source(
            "web_hallucinated"
        )


def test_rejects_naive_retrieval_timestamp():
    ledger = ResearchEvidenceLedger(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    naive_timestamp = datetime(
        2026,
        8,
        24,
        20,
        0,
    )

    with pytest.raises(
        ResearchEvidenceLedgerError
    ):
        ledger.record_web_search_result(
            make_result(),
            retrieved_at=naive_timestamp,
        )