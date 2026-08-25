import json
import time
from unittest.mock import Mock

import pytest

from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    BatchPageRetrievalResult,
    PageRetrievalResult,
    WebSearchItem,
    WebSearchResult,
)
from app.tools.crewai import (
    ControlledBatchPageRetrievalTool,
    ControlledWebSearchTool,
)
from app.tools.gateway import (
    ToolGateway,
)


def make_gateway() -> Mock:
    return Mock(spec=ToolGateway)


def make_search_result(
    *,
    query: str,
) -> WebSearchResult:
    return WebSearchResult(
        query=query,
        items=[
            WebSearchItem(
                source_id="web_test_source",
                title="Example Market Source",
                url="https://example.com/market",
                snippet="Example market evidence.",
            )
        ],
    )


def test_web_search_tool_routes_through_gateway():
    gateway = make_gateway()
    gateway.search_web.return_value = make_search_result(
        query="gym software Egypt"
    )

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=AnalysisStage.MARKET_RESEARCH,
    )

    raw_result = tool.run(
        query="gym software Egypt",
        max_results=3,
    )

    result = WebSearchResult.model_validate_json(
        raw_result
    )

    assert result.query == "gym software Egypt"
    assert len(result.items) == 1
    gateway.search_web.assert_called_once()

    call_kwargs = gateway.search_web.call_args.kwargs

    assert call_kwargs["stage"] == AnalysisStage.MARKET_RESEARCH
    assert call_kwargs["request"].query == "gym software Egypt"
    assert call_kwargs["request"].max_results == 3


def test_web_search_tool_rejects_invalid_max_results():
    gateway = make_gateway()

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=AnalysisStage.MARKET_RESEARCH,
    )

    with pytest.raises(ValueError):
        tool.run(
            query="gym software Egypt",
            max_results=100,
        )

    gateway.search_web.assert_not_called()


def test_web_search_tool_enforces_usage_limit():
    gateway = make_gateway()
    gateway.search_web.return_value = make_search_result(
        query="gym software Egypt"
    )

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=AnalysisStage.MARKET_RESEARCH,
        max_usage_count=1,
    )

    first_result = tool.run(
        query="gym software Egypt",
    )

    second_result = tool.run(
        query="another query",
    )

    assert "gym software Egypt" in first_result
    assert "usage limit" in second_result.lower()
    assert gateway.search_web.call_count == 1


def test_web_search_tool_records_evidence():
    gateway = make_gateway()
    gateway.search_web.return_value = make_search_result(
        query="gym software Egypt"
    )

    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.MARKET_RESEARCH
    )

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=AnalysisStage.MARKET_RESEARCH,
        evidence_ledger=ledger,
    )

    tool.run(
        query="gym software Egypt",
        max_results=3,
    )

    assert ledger.source_ids == (
        "web_test_source",
    )
    assert ledger.search_queries == (
        "gym software Egypt",
    )

    source = ledger.get_source(
        "web_test_source"
    )

    assert source.title == "Example Market Source"
    assert str(source.url) == "https://example.com/market"
    assert source.excerpt == "Example market evidence."
    assert source.retrieved_at is not None


def test_web_search_tool_rejects_mismatched_ledger_stage():
    gateway = make_gateway()
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    with pytest.raises(
        ValueError,
        match="Evidence ledger stage must match",
    ):
        ControlledWebSearchTool(
            gateway=gateway,
            stage=AnalysisStage.MARKET_RESEARCH,
            evidence_ledger=ledger,
        )


def test_batch_page_retrieval_routes_pages_and_records_ledger():
    gateway = make_gateway()

    def retrieve_page(*, stage, request):
        return PageRetrievalResult(
            source_id=(
                "web_one"
                if "one" in str(request.url)
                else "web_two"
            ),
            url=request.url,
            title="Official page",
            content=(
                "Pricing starts at $99/month "
                "with memberships and scheduling."
            ),
        )

    gateway.retrieve_page.side_effect = retrieve_page

    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    tool = ControlledBatchPageRetrievalTool(
        gateway=gateway,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
        evidence_ledger=ledger,
        max_workers=2,
    )

    raw_result = tool.run(
        urls=[
            "https://one.example/pricing",
            "https://two.example/features",
        ],
        max_chars=2_000,
    )

    result = BatchPageRetrievalResult.model_validate_json(
        raw_result
    )

    assert len(result.pages) == 2
    assert result.failures == []
    assert gateway.retrieve_page.call_count == 2
    assert ledger.page_retrieval_urls == (
        "https://one.example/pricing",
        "https://two.example/features",
    )
    assert set(ledger.source_ids) == {
        "web_one",
        "web_two",
    }


def test_batch_page_retrieval_keeps_partial_success():
    gateway = make_gateway()

    def retrieve_page(*, stage, request):
        if "broken" in str(request.url):
            raise RuntimeError("site unavailable")

        return PageRetrievalResult(
            source_id="web_good",
            url=request.url,
            title="Good page",
            content="Useful competitor evidence.",
        )

    gateway.retrieve_page.side_effect = retrieve_page

    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    tool = ControlledBatchPageRetrievalTool(
        gateway=gateway,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
        evidence_ledger=ledger,
        max_workers=2,
    )

    result = BatchPageRetrievalResult.model_validate_json(
        tool.run(
            urls=[
                "https://good.example",
                "https://broken.example",
            ]
        )
    )

    assert len(result.pages) == 1
    assert len(result.failures) == 1
    assert result.failures[0].error_type == "RuntimeError"
    assert ledger.source_ids == ("web_good",)


def test_batch_page_retrieval_executes_concurrently():
    gateway = make_gateway()

    def retrieve_page(*, stage, request):
        time.sleep(0.15)
        return PageRetrievalResult(
            source_id=(
                "web_" + str(request.url).split("//")[1][0]
            ),
            url=request.url,
            title="Page",
            content="Evidence",
        )

    gateway.retrieve_page.side_effect = retrieve_page

    tool = ControlledBatchPageRetrievalTool(
        gateway=gateway,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
        max_workers=4,
    )

    started_at = time.perf_counter()

    raw_result = tool.run(
        urls=[
            "https://a.example",
            "https://b.example",
            "https://c.example",
            "https://d.example",
        ]
    )

    elapsed = time.perf_counter() - started_at

    parsed = json.loads(raw_result)

    assert len(parsed["pages"]) == 4
    assert elapsed < 0.45


def test_batch_page_retrieval_rejects_duplicate_urls():
    gateway = make_gateway()

    tool = ControlledBatchPageRetrievalTool(
        gateway=gateway,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
    )

    with pytest.raises(ValueError):
        tool.run(
            urls=[
                "https://same.example",
                "https://same.example",
            ]
        )

    gateway.retrieve_page.assert_not_called()
