from unittest.mock import Mock

import pytest

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    WebSearchItem,
    WebSearchResult,
)
from app.tools.crewai import (
    ControlledWebSearchTool,
)
from app.tools.gateway import (
    ToolGateway,
)


def make_gateway() -> Mock:
    return Mock(
        spec=ToolGateway
    )


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
                url=(
                    "https://example.com/"
                    "market"
                ),
                snippet=(
                    "Example market evidence."
                ),
            )
        ],
    )


def test_web_search_tool_routes_through_gateway():
    gateway = make_gateway()

    gateway.search_web.return_value = (
        make_search_result(
            query="gym software Egypt"
        )
    )

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=(
            AnalysisStage.MARKET_RESEARCH
        ),
    )

    raw_result = tool.run(
        query="gym software Egypt",
        max_results=3,
    )

    result = (
        WebSearchResult
        .model_validate_json(
            raw_result
        )
    )

    assert (
        result.query
        == "gym software Egypt"
    )

    assert len(result.items) == 1

    gateway.search_web.assert_called_once()

    call_kwargs = (
        gateway
        .search_web
        .call_args
        .kwargs
    )

    assert (
        call_kwargs["stage"]
        == AnalysisStage.MARKET_RESEARCH
    )

    request = call_kwargs[
        "request"
    ]

    assert (
        request.query
        == "gym software Egypt"
    )

    assert request.max_results == 3


def test_web_search_tool_rejects_invalid_max_results():
    gateway = make_gateway()

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=(
            AnalysisStage.MARKET_RESEARCH
        ),
    )

    with pytest.raises(
        ValueError
    ):
        tool.run(
            query="gym software Egypt",
            max_results=100,
        )

    gateway.search_web.assert_not_called()


def test_web_search_tool_enforces_usage_limit():
    gateway = make_gateway()

    gateway.search_web.return_value = (
        make_search_result(
            query="gym software Egypt"
        )
    )

    tool = ControlledWebSearchTool(
        gateway=gateway,
        stage=(
            AnalysisStage.MARKET_RESEARCH
        ),
        max_usage_count=1,
    )

    first_result = tool.run(
        query="gym software Egypt",
    )

    second_result = tool.run(
        query="another query",
    )

    assert (
        "gym software Egypt"
        in first_result
    )

    assert (
        "usage limit"
        in second_result.lower()
    )

    assert (
        gateway
        .search_web
        .call_count
        == 1
    )