import httpx
from pydantic import (
    SecretStr,
    ValidationError,
)

from app.core.config import settings
from app.schemas.tools import (
    PageRetrievalRequest,
    PageRetrievalResult,
    WebSearchItem,
    WebSearchRequest,
    WebSearchResult,
)
from app.tools.source_ids import (
    build_web_source_id,
)


class FirecrawlProviderError(
    RuntimeError
):
    pass


class FirecrawlConfigurationError(
    FirecrawlProviderError
):
    pass


def _resolve_api_key(
    api_key: str | SecretStr | None,
) -> str:
    resolved_api_key = (
        api_key
        if api_key is not None
        else settings.firecrawl_api_key
    )

    if resolved_api_key is None:
        raise FirecrawlConfigurationError(
            "FIRECRAWL_API_KEY "
            "is not configured"
        )

    if isinstance(
        resolved_api_key,
        SecretStr,
    ):
        return (
            resolved_api_key
            .get_secret_value()
        )

    return resolved_api_key


class FirecrawlWebSearchProvider:
    SEARCH_URL = (
        "https://api.firecrawl.dev/v2/search"
    )

    def __init__(
        self,
        *,
        api_key: (
            str
            | SecretStr
            | None
        ) = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(
            api_key
        )

        self._client = (
            client
            if client is not None
            else httpx.Client(
                timeout=12.0,
            )
        )

    def search(
        self,
        request: WebSearchRequest,
    ) -> WebSearchResult:
        try:
            response = self._client.post(
                self.SEARCH_URL,
                headers={
                    "Authorization": (
                        f"Bearer {self._api_key}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                },
                json={
                    "query": request.query,
                    "limit": (
                        request.max_results
                    ),
                    "sources": [
                        "web"
                    ],
                    "safe": True,
                    "highlights": False,
                    "ignoreInvalidURLs": True,
                    "timeout": 8_000,
                },
            )

            response.raise_for_status()

            payload = response.json()

        except (
            httpx.HTTPError,
            ValueError,
        ) as exc:
            raise FirecrawlProviderError(
                "Firecrawl search request failed"
            ) from exc

        if payload.get("success") is not True:
            raise FirecrawlProviderError(
                "Firecrawl returned an "
                "unsuccessful response"
            )

        data = payload.get(
            "data",
            {},
        )

        raw_results = data.get(
            "web",
            [],
        )

        if not isinstance(
            raw_results,
            list,
        ):
            raise FirecrawlProviderError(
                "Firecrawl returned invalid "
                "web search data"
            )

        items: list[WebSearchItem] = []

        for raw_result in raw_results[
            :request.max_results
        ]:
            if not isinstance(
                raw_result,
                dict,
            ):
                continue

            title = raw_result.get(
                "title"
            )

            url = raw_result.get(
                "url"
            )

            if not title or not url:
                continue

            try:
                item = WebSearchItem(
                    source_id=(
                        build_web_source_id(
                            url
                        )
                    ),
                    title=title,
                    url=url,
                    snippet=(
                        raw_result.get(
                            "description"
                        )
                    ),
                )

            except ValidationError:
                continue

            items.append(item)

        return WebSearchResult(
            query=request.query,
            items=items,
        )


class FirecrawlPageRetrievalProvider:
    SCRAPE_URL = (
        "https://api.firecrawl.dev/v2/scrape"
    )

    def __init__(
        self,
        *,
        api_key: (
            str
            | SecretStr
            | None
        ) = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = _resolve_api_key(
            api_key
        )

        self._client = (
            client
            if client is not None
            else httpx.Client(
                timeout=12.0,
            )
        )

    def retrieve(
        self,
        request: PageRetrievalRequest,
    ) -> PageRetrievalResult:
        url = str(request.url)

        try:
            response = self._client.post(
                self.SCRAPE_URL,
                headers={
                    "Authorization": (
                        f"Bearer {self._api_key}"
                    ),
                    "Content-Type": (
                        "application/json"
                    ),
                },
                json={
                    "url": url,
                    "formats": [
                        "markdown"
                    ],
                    "onlyMainContent": True,
                    "removeBase64Images": True,
                    "blockAds": True,
                    "storeInCache": True,
                    "maxAge": 86_400_000,
                    "timeout": 8_000,
                },
            )

            response.raise_for_status()

            payload = response.json()

        except (
            httpx.HTTPError,
            ValueError,
        ) as exc:
            raise FirecrawlProviderError(
                "Firecrawl page retrieval failed"
            ) from exc

        if payload.get("success") is not True:
            raise FirecrawlProviderError(
                "Firecrawl returned an "
                "unsuccessful scrape response"
            )

        data = payload.get(
            "data",
            {},
        )

        if not isinstance(
            data,
            dict,
        ):
            raise FirecrawlProviderError(
                "Firecrawl returned invalid "
                "page retrieval data"
            )

        markdown = data.get(
            "markdown"
        )

        if not isinstance(
            markdown,
            str,
        ) or not markdown.strip():
            raise FirecrawlProviderError(
                "Firecrawl page retrieval "
                "returned no markdown content"
            )

        metadata = data.get(
            "metadata",
            {},
        )

        title = None

        if isinstance(
            metadata,
            dict,
        ):
            raw_title = metadata.get(
                "title"
            )

            if isinstance(
                raw_title,
                str,
            ) and raw_title.strip():
                title = raw_title.strip()

        return PageRetrievalResult(
            source_id=(
                build_web_source_id(
                    url
                )
            ),
            url=request.url,
            title=title,
            content=(
                markdown[
                    :request.max_chars
                ]
            ),
        )
