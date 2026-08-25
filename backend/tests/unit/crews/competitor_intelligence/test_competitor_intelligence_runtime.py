from unittest.mock import Mock

from app.crews.competitor_intelligence.runtime import (
    build_competitor_intelligence_runner,
)
from app.llm.gateway import (
    LLMGateway,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchRequest,
    WebSearchResult,
)


class FakeSearchProvider:
    def __init__(
        self,
    ) -> None:
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
                    source_id=(
                        "web_competitor_test"
                    ),
                    title=(
                        "Competitor Pricing"
                    ),
                    url=(
                        "https://"
                        "competitor.example/"
                        "pricing"
                    ),
                    snippet=(
                        "Published competitor "
                        "pricing evidence."
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
        build_competitor_intelligence_runner(
            llm_gateway=llm_gateway,
            web_search_provider=(
                search_provider
            ),
            model="test-model",
        )
    )

    assert (
        runner.evidence_ledger.stage
        == (
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    crew = runner.build_crew()

    assert (
        crew.agents[0].llm.model
        == "test-model"
    )

    research_task = crew.tasks[0]

    tool = research_task.tools[0]

    raw_result = tool.run(
        query=(
            "gym management software "
            "competitors Egypt"
        ),
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
        == "web_competitor_test"
    )

    assert (
        len(search_provider.requests)
        == 1
    )

    assert (
        search_provider
        .requests[0]
        .query
        == (
            "gym management software "
            "competitors Egypt"
        )
    )

    assert (
        runner
        .evidence_ledger
        .source_ids
        == (
            "web_competitor_test",
        )
    )

    canonical_source = (
        runner
        .evidence_ledger
        .get_source(
            "web_competitor_test"
        )
    )

    assert (
        str(canonical_source.url)
        == (
            "https://"
            "competitor.example/pricing"
        )
    )

    assert (
        canonical_source.title
        == "Competitor Pricing"
    )

    assert (
        canonical_source.excerpt
        == (
            "Published competitor "
            "pricing evidence."
        )
    )

    assert (
        canonical_source.retrieved_at
        is not None
    )