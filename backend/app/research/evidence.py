from datetime import (
    datetime,
    timezone,
)

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    EvidenceProvenance,
    ResearchEvidenceSource,
)
from app.schemas.tools import (
    PageRetrievalResult,
    WebSearchResult,
)
from app.tools.source_ids import (
    build_web_source_id,
)


class ResearchEvidenceLedgerError(
    RuntimeError
):
    pass


class EvidenceSourceCollisionError(
    ResearchEvidenceLedgerError
):
    pass


class UnknownEvidenceSourceError(
    ResearchEvidenceLedgerError
):
    pass


def _resolve_retrieved_at(
    retrieved_at: datetime | None,
) -> datetime:
    recorded_at = (
        retrieved_at
        if retrieved_at is not None
        else datetime.now(
            timezone.utc
        )
    )

    if (
        recorded_at.tzinfo is None
        or recorded_at.utcoffset()
        is None
    ):
        raise ResearchEvidenceLedgerError(
            "Evidence retrieval timestamp "
            "must be timezone-aware"
        )

    return recorded_at


class ResearchEvidenceLedger:
    def __init__(
        self,
        *,
        stage: AnalysisStage,
    ) -> None:
        self._stage = stage

        self._sources: dict[
            str,
            ResearchEvidenceSource,
        ] = {}

        self._search_queries: list[str] = []
        self._page_retrieval_urls: list[
            str
        ] = []

    @property
    def stage(
        self,
    ) -> AnalysisStage:
        return self._stage

    @property
    def search_queries(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._search_queries
        )

    @property
    def page_retrieval_urls(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._page_retrieval_urls
        )

    @property
    def source_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self._sources.keys()
        )

    def record_web_search_result(
        self,
        result: WebSearchResult,
        *,
        retrieved_at: datetime | None = None,
    ) -> None:
        recorded_at = _resolve_retrieved_at(
            retrieved_at
        )

        self._search_queries.append(
            result.query
        )

        for item in result.items:
            source = ResearchEvidenceSource(
                source_id=item.source_id,
                provenance=(
                    EvidenceProvenance.WEB
                ),
                title=item.title,
                url=item.url,
                retrieved_at=recorded_at,
                excerpt=item.snippet,
            )

            existing = self._sources.get(
                item.source_id
            )

            if existing is not None:
                if (
                    str(existing.url)
                    != str(source.url)
                ):
                    raise (
                        EvidenceSourceCollisionError(
                            "Evidence source ID "
                            f"{item.source_id!r} "
                            "was returned for "
                            "multiple URLs"
                        )
                    )

                continue

            self._sources[
                item.source_id
            ] = source

    def record_page_retrieval_result(
        self,
        result: PageRetrievalResult,
        *,
        retrieved_at: datetime | None = None,
    ) -> None:
        recorded_at = _resolve_retrieved_at(
            retrieved_at
        )

        url = str(result.url)

        source_id = (
            result.source_id
            if result.source_id is not None
            else build_web_source_id(url)
        )

        self._page_retrieval_urls.append(
            url
        )

        existing = self._sources.get(
            source_id
        )

        if (
            existing is not None
            and str(existing.url) != url
        ):
            raise EvidenceSourceCollisionError(
                "Evidence source ID "
                f"{source_id!r} was returned "
                "for multiple URLs"
            )

        title = (
            result.title
            if result.title is not None
            else (
                existing.title
                if existing is not None
                else url
            )
        )

        source = ResearchEvidenceSource(
            source_id=source_id,
            provenance=EvidenceProvenance.WEB,
            title=title,
            url=result.url,
            retrieved_at=recorded_at,
            excerpt=result.content[:2000],
        )

        self._sources[
            source_id
        ] = source

    def get_source(
        self,
        source_id: str,
    ) -> ResearchEvidenceSource:
        source = self._sources.get(
            source_id
        )

        if source is None:
            raise UnknownEvidenceSourceError(
                "Evidence source ID "
                f"{source_id!r} "
                "was not returned by a "
                "controlled research tool"
            )

        return source.model_copy(
            deep=True
        )

    def get_sources(
        self,
        source_ids: list[str],
    ) -> list[
        ResearchEvidenceSource
    ]:
        return [
            self.get_source(
                source_id
            )
            for source_id
            in source_ids
        ]
