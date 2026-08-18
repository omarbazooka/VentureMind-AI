from datetime import datetime
from enum import StrEnum

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class EvidenceProvenance(StrEnum):
    USER = "USER"
    FILE = "FILE"
    WEB = "WEB"
    CALCULATED = "CALCULATED"
    AI_ASSUMPTION = "AI_ASSUMPTION"


class ResearchClaimKind(StrEnum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"


class ResearchEvidenceQuality(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"


class ResearchEvidenceSource(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    source_id: str = Field(
        min_length=1,
        max_length=200,
    )

    provenance: EvidenceProvenance

    title: str = Field(
        min_length=1,
        max_length=500,
    )

    url: AnyHttpUrl | None = None

    retrieved_at: datetime | None = None

    excerpt: str | None = Field(
        default=None,
        max_length=2000,
    )

    @model_validator(mode="after")
    def validate_source(
        self,
    ) -> "ResearchEvidenceSource":
        if (
            self.provenance
            == EvidenceProvenance.WEB
            and self.url is None
        ):
            raise ValueError(
                "WEB evidence must include a URL"
            )

        return self


class BaseResearchFinding(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    statement: str = Field(
        min_length=1,
        max_length=2000,
    )

    claim_kind: ResearchClaimKind

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    evidence_source_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    is_numerical: bool = False

    @model_validator(mode="after")
    def validate_observed_claim(
        self,
    ) -> "BaseResearchFinding":
        if (
            self.claim_kind
            == ResearchClaimKind.OBSERVED
            and not self.evidence_source_ids
        ):
            raise ValueError(
                "Observed research findings "
                "must reference evidence"
            )

        return self


class MarketFindingCategory(StrEnum):
    MARKET_SIZE = "MARKET_SIZE"
    DEMAND_SIGNAL = "DEMAND_SIGNAL"
    TREND = "TREND"
    BARRIER = "BARRIER"
    REGULATION = "REGULATION"
    DISTRIBUTION = "DISTRIBUTION"
    OTHER = "OTHER"


class CompetitorFindingCategory(StrEnum):
    COMPETITOR = "COMPETITOR"
    PRODUCT = "PRODUCT"
    PRICING = "PRICING"
    POSITIONING = "POSITIONING"
    AUDIENCE = "AUDIENCE"
    WHITESPACE = "WHITESPACE"
    OTHER = "OTHER"


class CustomerFindingCategory(StrEnum):
    SEGMENT = "SEGMENT"
    PAIN_POINT = "PAIN_POINT"
    ALTERNATIVE = "ALTERNATIVE"
    BUYING_BEHAVIOR = "BUYING_BEHAVIOR"
    DEMAND_SIGNAL = "DEMAND_SIGNAL"
    VALUE_PROPOSITION = "VALUE_PROPOSITION"
    OTHER = "OTHER"


class MarketFinding(BaseResearchFinding):
    category: MarketFindingCategory


class CompetitorFinding(BaseResearchFinding):
    category: CompetitorFindingCategory


class CustomerFinding(BaseResearchFinding):
    category: CustomerFindingCategory


def _validate_result_evidence(
    *,
    findings: list[BaseResearchFinding],
    evidence_sources: list[
        ResearchEvidenceSource
    ],
    evidence_quality: ResearchEvidenceQuality,
    limitations: list[str],
) -> None:
    source_ids = [
        source.source_id
        for source in evidence_sources
    ]

    if len(source_ids) != len(
        set(source_ids)
    ):
        raise ValueError(
            "Evidence source IDs must be unique"
        )

    known_source_ids = set(source_ids)

    for finding in findings:
        unknown_source_ids = (
            set(
                finding.evidence_source_ids
            )
            - known_source_ids
        )

        if unknown_source_ids:
            raise ValueError(
                "Finding references unknown "
                "evidence source IDs: "
                f"{sorted(unknown_source_ids)}"
            )

    if (
        not findings
        and evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
    ):
        raise ValueError(
            "A result without findings must "
            "be marked INSUFFICIENT"
        )

    if (
        evidence_quality
        == ResearchEvidenceQuality.INSUFFICIENT
        and not limitations
    ):
        raise ValueError(
            "Insufficient evidence must "
            "explain its limitations"
        )


class MarketAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    findings: list[MarketFinding] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_sources: list[
        ResearchEvidenceSource
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_quality: ResearchEvidenceQuality

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "MarketAnalysis":
        _validate_result_evidence(
            findings=self.findings,
            evidence_sources=(
                self.evidence_sources
            ),
            evidence_quality=(
                self.evidence_quality
            ),
            limitations=self.limitations,
        )

        return self


class CompetitorAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    findings: list[
        CompetitorFinding
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_sources: list[
        ResearchEvidenceSource
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_quality: ResearchEvidenceQuality

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "CompetitorAnalysis":
        _validate_result_evidence(
            findings=self.findings,
            evidence_sources=(
                self.evidence_sources
            ),
            evidence_quality=(
                self.evidence_quality
            ),
            limitations=self.limitations,
        )

        return self


class CustomerAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    findings: list[
        CustomerFinding
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_sources: list[
        ResearchEvidenceSource
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_quality: ResearchEvidenceQuality

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> "CustomerAnalysis":
        _validate_result_evidence(
            findings=self.findings,
            evidence_sources=(
                self.evidence_sources
            ),
            evidence_quality=(
                self.evidence_quality
            ),
            limitations=self.limitations,
        )

        return self