from unittest.mock import Mock

from app.crews.competitor_intelligence.runtime import (
    build_competitor_intelligence_runner,
)
from app.llm.gateway import LLMGateway
from app.schemas.analysis import AnalysisStage
from app.schemas.tools import (
    BatchPageRetrievalResult,
    PageRetrievalRequest,
    PageRetrievalResult,
    WebSearchItem,
    WebSearchRequest,
    WebSearchResult,
)


class FakeSearchProvider:
    def __init__(self) -> None:
        self.requests: list[WebSearchRequest] = []

    def search(
        self,
        request: WebSearchRequest,
    ) -> WebSearchResult:
        self.requests.append(request)

        return WebSearchResult(
            query=request.query,
            items=[
                WebSearchItem(
                    source_id="web_competitor_test",
                    title="Competitor Pricing",
                    url="https://competitor.example/pricing",
                    snippet="Published pricing evidence.",
                )
            ],
        )


class FakePageProvider:
    def __init__(self) -> None:
        self.requests: list[PageRetrievalRequest] = []

    def retrieve(
        self,
        request: PageRetrievalRequest,
    ) -> PageRetrievalResult:
        self.requests.append(request)

        return PageRetrievalResult(
            source_id="web_competitor_test",
            url=request.url,
            title="Official Competitor Pricing",
            content=(
                "Memberships, scheduling, and "
                "pricing from $99/month."
            ),
        )


def test_runtime_wires_fast_search_and_page_retrieval():
    llm_gateway = Mock(spec=LLMGateway)
    search_provider = FakeSearchProvider()
    page_provider = FakePageProvider()

    runner = build_competitor_intelligence_runner(
        llm_gateway=llm_gateway,
        web_search_provider=search_provider,
        page_retrieval_provider=page_provider,
        model="test-model",
    )

    assert (
        runner.evidence_ledger.stage
        == AnalysisStage.COMPETITOR_INTELLIGENCE
    )

    crew = runner.build_crew()

    assert crew.agents[0].llm.model == "test-model"

    research_task = crew.tasks[0]
    assert len(research_task.tools) == 2

    search_tool = research_task.tools[0]
    page_tool = research_task.tools[1]

    raw_search = search_tool.run(
        query="gym management software Egypt",
        max_results=8,
    )

    search_result = WebSearchResult.model_validate_json(
        raw_search
    )

    assert search_result.items[0].source_id == "web_competitor_test"
    assert len(search_provider.requests) == 1
    assert search_provider.requests[0].max_results == 8

    raw_pages = page_tool.run(
        urls=[
            "https://competitor.example/pricing"
        ],
        max_chars=3_000,
    )

    page_result = BatchPageRetrievalResult.model_validate_json(
        raw_pages
    )

    assert len(page_result.pages) == 1
    assert page_result.failures == []
    assert len(page_provider.requests) == 1

    assert runner.evidence_ledger.search_queries == (
        "gym management software Egypt",
    )
    assert runner.evidence_ledger.page_retrieval_urls == (
        "https://competitor.example/pricing",
    )
    assert runner.evidence_ledger.source_ids == (
        "web_competitor_test",
    )

    canonical_source = runner.evidence_ledger.get_source(
        "web_competitor_test"
    )

    assert canonical_source.title == "Official Competitor Pricing"
    assert "$99/month" in canonical_source.excerpt
    assert canonical_source.retrieved_at is not None
