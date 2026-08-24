from enum import StrEnum
from typing import Protocol

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    PageRetrievalRequest,
    PageRetrievalResult,
    WebSearchRequest,
    WebSearchResult,
)


class ToolName(StrEnum):
    WEB_SEARCH = "WEB_SEARCH"
    PAGE_RETRIEVAL = "PAGE_RETRIEVAL"


RESEARCH_TOOL_PERMISSIONS = {
    AnalysisStage.MARKET_RESEARCH: {
        ToolName.WEB_SEARCH,
        ToolName.PAGE_RETRIEVAL,
    },
    AnalysisStage.COMPETITOR_INTELLIGENCE: {
        ToolName.WEB_SEARCH,
        ToolName.PAGE_RETRIEVAL,
    },
    AnalysisStage.CUSTOMER_INTELLIGENCE: {
        ToolName.WEB_SEARCH,
        ToolName.PAGE_RETRIEVAL,
    },
}


class WebSearchProvider(Protocol):
    def search(
        self,
        request: WebSearchRequest,
    ) -> WebSearchResult:
        ...


class PageRetrievalProvider(Protocol):
    def retrieve(
        self,
        request: PageRetrievalRequest,
    ) -> PageRetrievalResult:
        ...


class ToolGatewayError(RuntimeError):
    pass


class ToolPermissionError(
    ToolGatewayError
):
    pass


class ToolGateway:
    def __init__(
        self,
        *,
        web_search_provider: WebSearchProvider,
        page_retrieval_provider: PageRetrievalProvider,
    ) -> None:
        self._web_search_provider = (
            web_search_provider
        )

        self._page_retrieval_provider = (
            page_retrieval_provider
        )

    def _ensure_allowed(
        self,
        *,
        stage: AnalysisStage,
        tool: ToolName,
    ) -> None:
        allowed_tools = (
            RESEARCH_TOOL_PERMISSIONS
            .get(stage, set())
        )

        if tool not in allowed_tools:
            raise ToolPermissionError(
                f"{tool.value} is not allowed "
                f"for stage {stage.value}"
            )

    def search_web(
        self,
        *,
        stage: AnalysisStage,
        request: WebSearchRequest,
    ) -> WebSearchResult:
        self._ensure_allowed(
            stage=stage,
            tool=ToolName.WEB_SEARCH,
        )

        return (
            self._web_search_provider
            .search(request)
        )

    def retrieve_page(
        self,
        *,
        stage: AnalysisStage,
        request: PageRetrievalRequest,
    ) -> PageRetrievalResult:
        self._ensure_allowed(
            stage=stage,
            tool=ToolName.PAGE_RETRIEVAL,
        )

        return (
            self._page_retrieval_provider
            .retrieve(request)
        )