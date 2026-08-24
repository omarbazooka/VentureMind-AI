from unittest.mock import Mock

import pytest

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    WebSearchRequest,
    WebSearchResult,
)
from app.tools.gateway import (
    ToolGateway,
    ToolProviderNotConfiguredError,
)


def test_gateway_supports_search_only_configuration():
    search_provider = Mock()

    search_provider.search.return_value = (
        WebSearchResult(
            query="gym software Egypt",
            items=[],
        )
    )

    gateway = ToolGateway(
        web_search_provider=search_provider,
    )

    request = WebSearchRequest(
        query="gym software Egypt"
    )

    result = gateway.search_web(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        ),
        request=request,
    )

    assert (
        result.query
        == "gym software Egypt"
    )

    search_provider.search.assert_called_once_with(
        request
    )


def test_gateway_rejects_missing_search_provider():
    gateway = ToolGateway()

    with pytest.raises(
        ToolProviderNotConfiguredError
    ):
        gateway.search_web(
            stage=(
                AnalysisStage
                .MARKET_RESEARCH
            ),
            request=WebSearchRequest(
                query="gym software Egypt"
            ),
        )