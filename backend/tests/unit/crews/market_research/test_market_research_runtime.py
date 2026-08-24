from unittest.mock import Mock

from app.crews.market_research.runtime import (
    build_market_research_runner,
)
from app.llm.gateway import (
    LLMGateway,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchRequest,
    WebSearchResult,
)


class FakeSearchProvider:
    def __init__(self) -> None:
        self.requests: list[
            WebSearchRequest
        ] = []

    def search(
        self,
        request: WebSearchRequest,
    ) -> WebSearchResult:
        self.requests.append(
            request
        )

        return WebSearchResult(
            query=request.query,
            items=[
                WebSearchItem(
                    source_id="web_test",
                    title="Test source",
                    url=(
                        "https://real-source.example/"
                        "market"
                    ),
                    snippet=(
                        "Test market evidence"
                    ),
                )
            ],
        )


def test_runtime_wires_controlled_search_and_shared_ledger():
    llm_gateway = Mock(
        spec=LLMGateway
    )

    search_provider = (
        FakeSearchProvider()
    )

    runner = (
        build_market_research_runner(
            llm_gateway=llm_gateway,
            web_search_provider=(
                search_provider
            ),
            model="test-model",
        )
    )

    crew = runner.build_crew()

    assert (
        crew.agents[0].llm.model
        == "test-model"
    )

    tool = crew.tasks[0].tools[0]

    raw_result = tool.run(
        query="gym software Egypt",
        max_results=1,
    )

    result = (
        WebSearchResult
        .model_validate_json(
            raw_result
        )
    )

    assert (
        result.items[0].source_id
        == "web_test"
    )

    assert len(
        search_provider.requests
    ) == 1

    assert (
        search_provider
        .requests[0]
        .query
        == "gym software Egypt"
    )

    assert runner.evidence_ledger.source_ids == (
        "web_test",
    )

    canonical_source = (
        runner.evidence_ledger.get_source(
            "web_test"
        )
    )

    assert (
        str(canonical_source.url)
        == (
            "https://real-source.example/"
            "market"
        )
    )

    assert (
        canonical_source.retrieved_at
        is not None
    )
