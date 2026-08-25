from concurrent.futures import (
    ThreadPoolExecutor,
)

from crewai.tools.base_tool import (
    BaseTool,
)
from pydantic import (
    BaseModel,
    PrivateAttr,
)

from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.tools import (
    BatchPageRetrievalRequest,
    BatchPageRetrievalResult,
    PageRetrievalFailure,
    PageRetrievalRequest,
    PageRetrievalResult,
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

    _evidence_ledger: (
        ResearchEvidenceLedger | None
    ) = PrivateAttr(
        default=None
    )

    def __init__(
        self,
        *,
        gateway: ToolGateway,
        stage: AnalysisStage,
        evidence_ledger: (
            ResearchEvidenceLedger | None
        ) = None,
        max_usage_count: int = 4,
    ) -> None:
        if (
            evidence_ledger is not None
            and evidence_ledger.stage
            != stage
        ):
            raise ValueError(
                "Evidence ledger stage "
                "must match controlled "
                "tool stage"
            )

        super().__init__(
            max_usage_count=max_usage_count,
        )

        self._gateway = gateway
        self._stage = stage
        self._evidence_ledger = (
            evidence_ledger
        )

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

        if (
            self._evidence_ledger
            is not None
        ):
            (
                self._evidence_ledger
                .record_web_search_result(
                    result
                )
            )

        return result.model_dump_json()


class ControlledBatchPageRetrievalTool(
    BaseTool
):
    name: str = (
        "controlled_batch_page_retrieval"
    )

    description: str = (
        "Retrieve the detailed content of up to "
        "four known web pages concurrently. Use "
        "this after search discovery to inspect "
        "official product, feature, pricing, or "
        "positioning pages without running more "
        "web searches."
    )

    args_schema: type[BaseModel] = (
        BatchPageRetrievalRequest
    )

    _gateway: ToolGateway = PrivateAttr()
    _stage: AnalysisStage = PrivateAttr()
    _evidence_ledger: (
        ResearchEvidenceLedger | None
    ) = PrivateAttr(
        default=None
    )
    _max_workers: int = PrivateAttr()

    def __init__(
        self,
        *,
        gateway: ToolGateway,
        stage: AnalysisStage,
        evidence_ledger: (
            ResearchEvidenceLedger | None
        ) = None,
        max_usage_count: int = 2,
        max_workers: int = 4,
    ) -> None:
        if (
            evidence_ledger is not None
            and evidence_ledger.stage
            != stage
        ):
            raise ValueError(
                "Evidence ledger stage "
                "must match controlled "
                "tool stage"
            )

        if max_workers < 1:
            raise ValueError(
                "max_workers must be at least 1"
            )

        super().__init__(
            max_usage_count=max_usage_count,
        )

        self._gateway = gateway
        self._stage = stage
        self._evidence_ledger = (
            evidence_ledger
        )
        self._max_workers = max_workers

    def _retrieve_one(
        self,
        request: PageRetrievalRequest,
    ) -> PageRetrievalResult:
        return self._gateway.retrieve_page(
            stage=self._stage,
            request=request,
        )

    def _run(
        self,
        urls: list[str],
        max_chars: int = 6_000,
    ) -> str:
        batch_request = (
            BatchPageRetrievalRequest(
                urls=urls,
                max_chars=max_chars,
            )
        )

        requests = [
            PageRetrievalRequest(
                url=url,
                max_chars=(
                    batch_request.max_chars
                ),
            )
            for url in batch_request.urls
        ]

        pages: list[
            PageRetrievalResult
        ] = []

        failures: list[
            PageRetrievalFailure
        ] = []

        worker_count = min(
            self._max_workers,
            len(requests),
        )

        with ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:
            futures = [
                (
                    request,
                    executor.submit(
                        self._retrieve_one,
                        request,
                    ),
                )
                for request in requests
            ]

            for request, future in futures:
                try:
                    page = future.result()
                except Exception as exc:
                    failures.append(
                        PageRetrievalFailure(
                            url=request.url,
                            error_type=(
                                type(exc).__name__
                            ),
                        )
                    )
                    continue

                pages.append(page)

                if (
                    self._evidence_ledger
                    is not None
                ):
                    (
                        self._evidence_ledger
                        .record_page_retrieval_result(
                            page
                        )
                    )

        result = BatchPageRetrievalResult(
            pages=pages,
            failures=failures,
        )

        return result.model_dump_json()
