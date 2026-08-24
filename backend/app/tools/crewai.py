from pydantic import (
    BaseModel,
    PrivateAttr,
)
from crewai.tools.base_tool import (
    BaseTool,
)

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    WebSearchRequest,
)
from app.tools.gateway import (
    ToolGateway,
)


class ControlledWebSearchTool(
    BaseTool
):
    name: str = "controlled_web_search"

    description: str = (
        "Search the web for reliable external "
        "evidence relevant to the current "
        "research task. Use concise, specific "
        "search queries."
    )

    args_schema: type[BaseModel] = (
        WebSearchRequest
    )

    _gateway: ToolGateway = PrivateAttr()
    _stage: AnalysisStage = PrivateAttr()

    def __init__(
        self,
        *,
        gateway: ToolGateway,
        stage: AnalysisStage,
        max_usage_count: int = 4,
    ) -> None:
        super().__init__(
            max_usage_count=max_usage_count,
        )

        self._gateway = gateway
        self._stage = stage

    def _run(
        self,
        query: str,
        max_results: int = 5,
    ) -> str:
        request = WebSearchRequest(
            query=query,
            max_results=max_results,
        )

        result = (
            self._gateway.search_web(
                stage=self._stage,
                request=request,
            )
        )

        return result.model_dump_json()