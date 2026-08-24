import json

import httpx
import pytest

from app.schemas.tools import (
    WebSearchRequest,
)
from app.tools.providers.firecrawl import (
    FirecrawlProviderError,
    FirecrawlWebSearchProvider,
)


def test_firecrawl_maps_search_results():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url
            == (
                "https://api.firecrawl.dev/"
                "v2/search"
            )
        )

        assert (
            request.headers[
                "Authorization"
            ]
            == "Bearer test-key"
        )

        body = json.loads(
            request.content
        )

        assert (
            body["query"]
            == "gym software Egypt"
        )

        assert body["limit"] == 3

        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "web": [
                        {
                            "title": (
                                "Egypt Fitness "
                                "Market"
                            ),
                            "url": (
                                "https://"
                                "example.com/"
                                "egypt-market"
                            ),
                            "description": (
                                "Market evidence."
                            ),
                        }
                    ]
                },
            },
        )

    client = httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        )
    )

    provider = (
        FirecrawlWebSearchProvider(
            api_key="test-key",
            client=client,
        )
    )

    result = provider.search(
        WebSearchRequest(
            query="gym software Egypt",
            max_results=3,
        )
    )

    assert (
        result.query
        == "gym software Egypt"
    )

    assert len(result.items) == 1

    item = result.items[0]

    assert (
        item.title
        == "Egypt Fitness Market"
    )

    assert (
        item.snippet
        == "Market evidence."
    )

    assert item.source_id.startswith(
        "web_"
    )


def test_firecrawl_source_id_is_deterministic():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "web": [
                        {
                            "title": "Source",
                            "url": (
                                "https://"
                                "example.com/report"
                            ),
                            "description": (
                                "Evidence"
                            ),
                        }
                    ]
                },
            },
        )

    client = httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        )
    )

    provider = (
        FirecrawlWebSearchProvider(
            api_key="test-key",
            client=client,
        )
    )

    request = WebSearchRequest(
        query="test query"
    )

    first = provider.search(
        request
    )

    second = provider.search(
        request
    )

    assert (
        first.items[0].source_id
        == second.items[0].source_id
    )


def test_firecrawl_normalizes_http_error():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            500,
            json={
                "success": False,
                "error": "server exploded",
            },
        )

    client = httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        )
    )

    provider = (
        FirecrawlWebSearchProvider(
            api_key="test-key",
            client=client,
        )
    )

    with pytest.raises(
        FirecrawlProviderError
    ):
        provider.search(
            WebSearchRequest(
                query="test query"
            )
        )


def test_firecrawl_rejects_unsuccessful_payload():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": False,
                "error": "search failed",
            },
        )

    client = httpx.Client(
        transport=(
            httpx.MockTransport(
                handler
            )
        )
    )

    provider = (
        FirecrawlWebSearchProvider(
            api_key="test-key",
            client=client,
        )
    )

    with pytest.raises(
        FirecrawlProviderError
    ):
        provider.search(
            WebSearchRequest(
                query="test query"
            )
        )