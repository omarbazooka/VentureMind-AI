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
    WebSearchResult,
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