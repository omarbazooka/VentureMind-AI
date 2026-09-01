from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.analysis import AnalysisStage


RESEARCH_SUPPORT_STAGES = frozenset(
    {
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    }
)


class StrategicClaimKind(StrEnum):
    PROFILE_FACT = "PROFILE_FACT"
    RESEARCH_INFERENCE = "RESEARCH_INFERENCE"
    AI_ASSUMPTION = "AI_ASSUMPTION"


class StrategicInsight(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    statement: str = Field(
        min_length=1,
        max_length=2000,
    )

    claim_kind: StrategicClaimKind

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    supporting_stages: list[
        AnalysisStage
    ] = Field(
        default_factory=list,
        max_length=3,
    )

    evidence_source_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    profile_fields: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_grounding(
        self,
    ) -> "StrategicInsight":
        invalid_stages = (
            set(self.supporting_stages)
            - RESEARCH_SUPPORT_STAGES
        )

        if invalid_stages:
            raise ValueError(
                "Strategic insights may only "
                "reference research stages as "
                "supporting stages"
            )

        if (
            self.claim_kind
            == StrategicClaimKind.PROFILE_FACT
            and not self.profile_fields
        ):
            raise ValueError(
                "PROFILE_FACT strategic insights "
                "must reference at least one "
                "IdeaProfile field"
            )

        if (
            self.claim_kind
            == StrategicClaimKind.RESEARCH_INFERENCE
            and not self.supporting_stages
        ):
            raise ValueError(
                "RESEARCH_INFERENCE strategic "
                "insights must reference at least "
                "one supporting research stage"
            )

        return self


class BusinessStrategyAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    executive_summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    positioning: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    value_proposition: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    business_model_implications: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    go_to_market: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    strategic_strengths: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    strategic_weaknesses: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    critical_assumptions: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=15,
    )

    finance_questions: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )