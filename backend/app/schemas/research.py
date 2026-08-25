from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
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


class ResearchGateDecision(StrEnum):
    ACCEPT = "ACCEPT"
    RETRY = "RETRY"
    INSUFFICIENT = "INSUFFICIENT"


class ResearchGateIssueCode(StrEnum):
    STAGE_FAILED = "STAGE_FAILED"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


class ResearchStageGateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: AnalysisStage
    attempt: int = Field(ge=1)
    stage_status: AnalysisStageStatus
    evidence_quality: ResearchEvidenceQuality | None = None
    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    error_code: str | None = Field(
        default=None,
        max_length=100,
    )


class ResearchStageGateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: AnalysisStage
    attempt: int = Field(ge=1)
    stage_status: AnalysisStageStatus
    evidence_quality: ResearchEvidenceQuality | None = None
    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    retry_eligible: bool = False
    issue_codes: list[ResearchGateIssueCode] = Field(
        default_factory=list,
        max_length=10,
    )


class ResearchEvidenceGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ResearchGateDecision
    can_proceed: bool
    assessments: list[ResearchStageGateAssessment] = Field(
        min_length=3,
        max_length=10,
    )
    retry_stages: list[AnalysisStage] = Field(
        default_factory=list,
        max_length=10,
    )
    insufficient_stages: list[AnalysisStage] = Field(
        default_factory=list,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_gate_result(
        self,
    ) -> "ResearchEvidenceGateResult":
        if self.decision == ResearchGateDecision.ACCEPT:
            if (
                not self.can_proceed
                or self.retry_stages
                or self.insufficient_stages
            ):
                raise ValueError(
                    "ACCEPT requires can_proceed=True with no retry or insufficient stages"
                )

        if self.decision == ResearchGateDecision.RETRY:
            if self.can_proceed or not self.retry_stages:
                raise ValueError(
                    "RETRY requires can_proceed=False and at least one retry stage"
                )

        if self.decision == ResearchGateDecision.INSUFFICIENT:
            if not self.can_proceed or not self.insufficient_stages:
                raise ValueError(
                    "INSUFFICIENT requires can_proceed=True and explicit insufficient stages"
                )

        return self


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

    @field_serializer("url")
    def serialize_url(
        self,
        url: AnyHttpUrl | None,
    ) -> str | None:
        return str(url) if url is not None else None

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


class CompetitorRelationship(StrEnum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    SUBSTITUTE = "SUBSTITUTE"


class CompetitorDetail(BaseModel):
    """One evidence-aware competitor card detail."""

    model_config = ConfigDict(
        extra="forbid"
    )

    statement: str = Field(
        min_length=1,
        max_length=1200,
    )

    claim_kind: ResearchClaimKind

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    evidence_source_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
    )

    is_numerical: bool = False

    @model_validator(mode="after")
    def validate_detail(
        self,
    ) -> "CompetitorDetail":
        if (
            self.claim_kind
            == ResearchClaimKind.OBSERVED
            and not self.evidence_source_ids
        ):
            raise ValueError(
                "Observed competitor details "
                "must reference evidence"
            )

        if (
            self.is_numerical
            and not self.evidence_source_ids
        ):
            raise ValueError(
                "Numerical competitor details "
                "must reference evidence"
            )

        return self


class CompetitorProfile(BaseModel):
    """Frontend-ready structured profile for one competitor."""

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str = Field(
        min_length=1,
        max_length=200,
    )

    relationship: CompetitorRelationship

    relevance_summary: str = Field(
        min_length=1,
        max_length=1600,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    primary_source_id: str = Field(
        min_length=1,
        max_length=200,
    )

    strengths: list[CompetitorDetail] = Field(
        default_factory=list,
        max_length=6,
    )

    weaknesses: list[CompetitorDetail] = Field(
        default_factory=list,
        max_length=6,
    )

    pricing: CompetitorDetail | None = None
    positioning: CompetitorDetail | None = None
    target_audience: CompetitorDetail | None = None
    geography: CompetitorDetail | None = None


def _validate_result_evidence(
    *,
    findings: list[BaseResearchFinding],
    evidence_sources: list[
        ResearchEvidenceSource
    ],
    evidence_quality: ResearchEvidenceQuality,
    limitations: list[str],
    allow_empty_findings: bool = False,
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
        and not allow_empty_findings
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


def _competitor_profile_source_ids(
    competitor: CompetitorProfile,
) -> set[str]:
    source_ids = {
        competitor.primary_source_id
    }

    details: list[CompetitorDetail] = [
        *competitor.strengths,
        *competitor.weaknesses,
    ]

    for optional_detail in (
        competitor.pricing,
        competitor.positioning,
        competitor.target_audience,
        competitor.geography,
    ):
        if optional_detail is not None:
            details.append(optional_detail)

    for detail in details:
        source_ids.update(
            detail.evidence_source_ids
        )

    return source_ids


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

    competitors: list[
        CompetitorProfile
    ] = Field(
        default_factory=list,
        max_length=5,
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
            allow_empty_findings=True,
        )

        if (
            self.evidence_quality
            != ResearchEvidenceQuality.INSUFFICIENT
            and not self.competitors
        ):
            raise ValueError(
                "A non-insufficient Competitor "
                "analysis must include competitor "
                "profiles"
            )

        normalized_names = [
            competitor.name.strip().casefold()
            for competitor in self.competitors
        ]

        if len(normalized_names) != len(
            set(normalized_names)
        ):
            raise ValueError(
                "Competitor profile names "
                "must be unique"
            )

        known_source_ids = {
            source.source_id
            for source in self.evidence_sources
        }

        for competitor in self.competitors:
            unknown_source_ids = (
                _competitor_profile_source_ids(
                    competitor
                )
                - known_source_ids
            )

            if unknown_source_ids:
                raise ValueError(
                    "Competitor profile references "
                    "unknown evidence source IDs: "
                    f"{sorted(unknown_source_ids)}"
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


class ResearchStageClaim(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )

    stage_run_id: UUID
    analysis_run_id: UUID
    stage: AnalysisStage

    attempt: int = Field(
        ge=1,
    )

    profile_snapshot: AnalysisProfileSnapshot
