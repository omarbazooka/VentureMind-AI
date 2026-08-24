from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
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

    url: AnyHttpUrl

    title: str | None = Field(
        default=None,
        max_length=500,
    )

    content: str = Field(
        min_length=1,
        max_length=20_000,
    )