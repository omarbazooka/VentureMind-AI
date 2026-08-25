import json

import httpx
import pytest

from app.schemas.tools import (
    PageRetrievalRequest,
    WebSearchRequest,
)
from app.tools.providers.firecrawl import (
    FirecrawlPageRetrievalProvider,
    FirecrawlProviderError,
    FirecrawlWebSearchProvider,
)


def test_firecrawl_maps_search_results():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url
            == "https://api.firecrawl.dev/v2/search"
        )

        assert (
            request.headers["Authorization"]
            == "Bearer test-key"
        )

        body = json.loads(request.content)

        assert body["query"] == "gym software Egypt"
        assert body["limit"] == 3
        assert body["timeout"] == 8_000

        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "web": [
                        {
                            "title": "Egypt Fitness Market",
                            "url": (
                                "https://example.com/"
                                "egypt-market"
                            ),
                            "description": "Market evidence.",
                        }
                    ]
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = FirecrawlWebSearchProvider(
        api_key="test-key",
        client=client,
    )

    result = provider.search(
        WebSearchRequest(
            query="gym software Egypt",
            max_results=3,
        )
    )

    assert result.query == "gym software Egypt"
    assert len(result.items) == 1
    assert result.items[0].title == "Egypt Fitness Market"
    assert result.items[0].snippet == "Market evidence."
    assert result.items[0].source_id.startswith("web_")


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
                            "url": "https://example.com/report",
                            "description": "Evidence",
                        }
                    ]
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = FirecrawlWebSearchProvider(
        api_key="test-key",
        client=client,
    )

    request = WebSearchRequest(query="test query")

    first = provider.search(request)
    second = provider.search(request)

    assert (
        first.items[0].source_id
        == second.items[0].source_id
    )


def test_firecrawl_maps_page_retrieval():
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url
            == "https://api.firecrawl.dev/v2/scrape"
        )

        body = json.loads(request.content)

        assert body["url"] == "https://competitor.example/pricing"
        assert body["formats"] == ["markdown"]
        assert body["onlyMainContent"] is True
        assert body["storeInCache"] is True
        assert body["maxAge"] == 86_400_000
        assert body["timeout"] == 8_000

        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "markdown": (
                        "# Pricing\nStarter: $99/month"
                    ),
                    "metadata": {
                        "title": "Competitor Pricing"
                    },
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = FirecrawlPageRetrievalProvider(
        api_key="test-key",
        client=client,
    )

    result = provider.retrieve(
        PageRetrievalRequest(
            url="https://competitor.example/pricing",
            max_chars=1_000,
        )
    )

    assert result.source_id is not None
    assert result.source_id.startswith("web_")
    assert result.title == "Competitor Pricing"
    assert "$99/month" in result.content


def test_firecrawl_page_retrieval_limits_content():
    content = "x" * 3_000

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "markdown": content,
                    "metadata": {},
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = FirecrawlPageRetrievalProvider(
        api_key="test-key",
        client=client,
    )

    result = provider.retrieve(
        PageRetrievalRequest(
            url="https://competitor.example",
            max_chars=1_000,
        )
    )

    assert len(result.content) == 1_000


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
        transport=httpx.MockTransport(handler)
    )

    search_provider = FirecrawlWebSearchProvider(
        api_key="test-key",
        client=client,
    )

    page_provider = FirecrawlPageRetrievalProvider(
        api_key="test-key",
        client=client,
    )

    with pytest.raises(FirecrawlProviderError):
        search_provider.search(
            WebSearchRequest(query="test query")
        )

    with pytest.raises(FirecrawlProviderError):
        page_provider.retrieve(
            PageRetrievalRequest(
                url="https://example.com"
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
                "error": "failed",
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    search_provider = FirecrawlWebSearchProvider(
        api_key="test-key",
        client=client,
    )

    page_provider = FirecrawlPageRetrievalProvider(
        api_key="test-key",
        client=client,
    )

    with pytest.raises(FirecrawlProviderError):
        search_provider.search(
            WebSearchRequest(query="test query")
        )

    with pytest.raises(FirecrawlProviderError):
        page_provider.retrieve(
            PageRetrievalRequest(
                url="https://example.com"
            )
        )
