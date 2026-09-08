from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import (
    FinancialInputName,
    FinancialMetricName,
)


RISK_RESEARCH_STAGES = frozenset(
    {
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    }
)

RISK_UPSTREAM_SUPPORT_STAGES = frozenset(
    {
        *RISK_RESEARCH_STAGES,
        AnalysisStage.BUSINESS_STRATEGY,
        AnalysisStage.FINANCE,
        AnalysisStage.DECISION_ANALYTICS,
    }
)


class RiskCategory(StrEnum):
    MARKET = "MARKET"
    COMPETITIVE = "COMPETITIVE"
    CUSTOMER_DEMAND = "CUSTOMER_DEMAND"
    FINANCIAL = "FINANCIAL"
    EXECUTION = "EXECUTION"
    REGULATORY = "REGULATORY"
    TECHNOLOGY = "TECHNOLOGY"
    EVIDENCE_QUALITY = "EVIDENCE_QUALITY"


class RiskLikelihood(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskImpact(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


LIKELIHOOD_WEIGHT = {
    RiskLikelihood.LOW: 1,
    RiskLikelihood.MEDIUM: 2,
    RiskLikelihood.HIGH: 3,
}

IMPACT_WEIGHT = {
    RiskImpact.LOW: 1,
    RiskImpact.MEDIUM: 2,
    RiskImpact.HIGH: 3,
    RiskImpact.CRITICAL: 4,
}

RISK_LEVEL_ORDER = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}


def calculate_risk_score(
    likelihood: RiskLikelihood,
    impact: RiskImpact,
) -> int:
    return (
        LIKELIHOOD_WEIGHT[likelihood]
        * IMPACT_WEIGHT[impact]
    )


def risk_level_for_score(score: int) -> RiskLevel:
    if score <= 2:
        return RiskLevel.LOW
    if score <= 4:
        return RiskLevel.MEDIUM
    if score <= 8:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL


class RiskDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: RiskCategory
    title: str = Field(min_length=1, max_length=300)
    statement: str = Field(min_length=1, max_length=2000)
    likelihood: RiskLikelihood
    impact: RiskImpact
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1, max_length=3000)
    mitigation_actions: list[str] = Field(
        default_factory=list,
        max_length=10,
    )
    monitoring_signals: list[str] = Field(
        default_factory=list,
        max_length=10,
    )
    profile_fields: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    supporting_stages: list[AnalysisStage] = Field(
        default_factory=list,
        max_length=6,
    )
    evidence_source_ids: list[str] = Field(
        default_factory=list,
        max_length=20,
    )
    financial_metrics: list[FinancialMetricName] = Field(
        default_factory=list,
        max_length=10,
    )
    decision_kpis: list[DecisionKPIName] = Field(
        default_factory=list,
        max_length=10,
    )
    sensitivity_inputs: list[FinancialInputName] = Field(
        default_factory=list,
        max_length=10,
    )

    @field_validator("title", "statement", "rationale")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("required risk text cannot be blank")
        return normalized

    @model_validator(mode="after")
    def validate_grounding_declarations(self) -> "RiskDraft":
        invalid_stages = (
            set(self.supporting_stages)
            - RISK_UPSTREAM_SUPPORT_STAGES
        )
        if invalid_stages:
            raise ValueError(
                "Risk drafts may only reference upstream analysis stages"
            )

        has_lineage = any(
            (
                self.profile_fields,
                self.supporting_stages,
                self.evidence_source_ids,
                self.financial_metrics,
                self.decision_kpis,
                self.sensitivity_inputs,
            )
        )
        if not has_lineage:
            raise ValueError(
                "Risk drafts must declare at least one grounding reference"
            )

        if (
            self.evidence_source_ids
            and not (
                set(self.supporting_stages)
                & RISK_RESEARCH_STAGES
            )
        ):
            raise ValueError(
                "Evidence source IDs require a supporting research stage"
            )

        if (
            self.financial_metrics
            and AnalysisStage.FINANCE
            not in self.supporting_stages
        ):
            raise ValueError(
                "Financial metric references require FINANCE support"
            )

        if (
            (self.decision_kpis or self.sensitivity_inputs)
            and AnalysisStage.DECISION_ANALYTICS
            not in self.supporting_stages
        ):
            raise ValueError(
                "Analytics references require DECISION_ANALYTICS support"
            )

        for values, label in (
            (self.profile_fields, "profile_fields"),
            (self.supporting_stages, "supporting_stages"),
            (self.evidence_source_ids, "evidence_source_ids"),
            (self.financial_metrics, "financial_metrics"),
            (self.decision_kpis, "decision_kpis"),
            (self.sensitivity_inputs, "sensitivity_inputs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(
                    f"Risk {label} cannot contain duplicates"
                )

        return self


class RiskDraftAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(
        min_length=1,
        max_length=5000,
    )
    risks: list[RiskDraft] = Field(
        default_factory=list,
        max_length=20,
    )
    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_unique_risks(self) -> "RiskDraftAnalysis":
        keys = [
            (risk.category, risk.title.casefold())
            for risk in self.risks
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(
                "Risk draft analysis cannot contain duplicate category/title risks"
            )
        return self


class GroundedRisk(RiskDraft):
    risk_score: int = Field(ge=1, le=12)
    risk_level: RiskLevel

    @model_validator(mode="after")
    def validate_score_and_level(self) -> "GroundedRisk":
        expected_score = calculate_risk_score(
            self.likelihood,
            self.impact,
        )
        if self.risk_score != expected_score:
            raise ValueError(
                "risk_score must be derived from likelihood and impact"
            )

        expected_level = risk_level_for_score(expected_score)
        if self.risk_level != expected_level:
            raise ValueError(
                "risk_level must be derived from risk_score"
            )
        return self


class RiskAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(
        min_length=1,
        max_length=5000,
    )
    risks: list[GroundedRisk] = Field(
        default_factory=list,
        max_length=20,
    )
    overall_level: RiskLevel | None = None
    limitations: list[str] = Field(
        default_factory=list,
        max_length=30,
    )

    @model_validator(mode="after")
    def validate_overall_level(self) -> "RiskAnalysis":
        if not self.risks:
            if self.overall_level is not None:
                raise ValueError(
                    "Risk analysis without risks cannot declare an overall level"
                )
            return self

        if self.overall_level is None:
            raise ValueError(
                "Risk analysis with risks requires an overall level"
            )

        expected = max(
            (risk.risk_level for risk in self.risks),
            key=lambda level: RISK_LEVEL_ORDER[level],
        )
        if self.overall_level != expected:
            raise ValueError(
                "overall_level must equal the highest grounded risk level"
            )
        return self
