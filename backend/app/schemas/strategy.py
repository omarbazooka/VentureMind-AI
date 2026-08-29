from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
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

    supporting_stages: list[str] = Field(
        default_factory=list,
        max_length=3,
    )


class BusinessStrategyAnalysis(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    executive_summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    positioning: list[StrategicInsight] = Field(
        default_factory=list,
        max_length=10,
    )

    value_proposition: list[StrategicInsight] = Field(
        default_factory=list,
        max_length=10,
    )

    business_model_implications: list[
        StrategicInsight
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    go_to_market: list[StrategicInsight] = Field(
        default_factory=list,
        max_length=10,
    )

    strategic_strengths: list[StrategicInsight] = Field(
        default_factory=list,
        max_length=10,
    )

    strategic_weaknesses: list[StrategicInsight] = Field(
        default_factory=list,
        max_length=10,
    )

    critical_assumptions: list[StrategicInsight] = Field(
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