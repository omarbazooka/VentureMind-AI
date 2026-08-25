from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class WebSearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        min_length=1,
        max_length=500,
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=10,
    )


class WebSearchItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    source_id: str = Field(
        min_length=1,
        max_length=200,
    )

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    url: AnyHttpUrl

    snippet: str | None = Field(
        default=None,
        max_length=2000,
    )


class WebSearchResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    query: str = Field(
        min_length=1,
        max_length=500,
    )

    items: list[WebSearchItem] = Field(
        default_factory=list,
        max_length=10,
    )


class PageRetrievalRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    url: AnyHttpUrl

    max_chars: int = Field(
        default=12_000,
        ge=1_000,
        le=20_000,
    )


class PageRetrievalResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    source_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    url: AnyHttpUrl

    title: str | None = Field(
        default=None,
        max_length=500,
    )

    content: str = Field(
        min_length=1,
        max_length=20_000,
    )


class PageRetrievalFailure(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    url: AnyHttpUrl

    error_type: str = Field(
        min_length=1,
        max_length=200,
    )


class BatchPageRetrievalRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    urls: list[AnyHttpUrl] = Field(
        min_length=1,
        max_length=4,
    )

    max_chars: int = Field(
        default=6_000,
        ge=1_000,
        le=10_000,
    )

    @model_validator(mode="after")
    def validate_unique_urls(
        self,
    ) -> "BatchPageRetrievalRequest":
        normalized_urls = [
            str(url)
            for url in self.urls
        ]

        if len(normalized_urls) != len(
            set(normalized_urls)
        ):
            raise ValueError(
                "Batch page retrieval URLs "
                "must be unique"
            )

        return self


class BatchPageRetrievalResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    pages: list[PageRetrievalResult] = Field(
        default_factory=list,
        max_length=4,
    )

    failures: list[
        PageRetrievalFailure
    ] = Field(
        default_factory=list,
        max_length=4,
    )
