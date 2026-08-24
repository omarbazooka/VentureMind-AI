from hashlib import sha256

import httpx
from pydantic import (
    SecretStr,
    ValidationError,
)

from app.core.config import settings
from app.schemas.tools import (
    WebSearchItem,
    WebSearchRequest,
    WebSearchResult,
)


class FirecrawlProviderError(
    RuntimeError
):
    pass


class FirecrawlConfigurationError(
    FirecrawlProviderError
):
    pass


def _build_web_source_id(
    url: str,
) -> str:
    digest = sha256(
        url.encode("utf-8")
    ).hexdigest()

    return f"web_{digest[:16]}"


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
            resolved_api_key = (
                resolved_api_key
                .get_secret_value()
            )

        self._api_key = resolved_api_key

        self._client = (
            client
            if client is not None
            else httpx.Client(
                timeout=15.0,
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
                    "timeout": 10_000,
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
                        _build_web_source_id(
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