from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.analysis import AnalysisStage


DECISION_RESEARCH_STAGES = frozenset(
    {
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    }
)

DECISION_UPSTREAM_STAGES = frozenset(
    {
        *DECISION_RESEARCH_STAGES,
        AnalysisStage.BUSINESS_STRATEGY,
        AnalysisStage.FINANCE,
        AnalysisStage.DECISION_ANALYTICS,
        AnalysisStage.RISK,
        AnalysisStage.INDEPENDENT_VALIDATION,
    }
)


class VentureDecision(StrEnum):
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DecisionConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DecisionLineageKind(StrEnum):
    PROFILE_FIELD = "PROFILE_FIELD"
    EVIDENCE_SOURCE = "EVIDENCE_SOURCE"
    FINANCIAL_METRIC = "FINANCIAL_METRIC"
    DECISION_KPI = "DECISION_KPI"
    SENSITIVITY_INPUT = "SENSITIVITY_INPUT"
    RISK = "RISK"
    VALIDATION_ISSUE = "VALIDATION_ISSUE"
    STAGE_RESULT = "STAGE_RESULT"


class DecisionLineageReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: DecisionLineageKind
    value: str = Field(min_length=1, max_length=500)
    stage: AnalysisStage | None = None

    @model_validator(mode="after")
    def validate_stage_contract(self) -> "DecisionLineageReference":
        if self.kind == DecisionLineageKind.PROFILE_FIELD:
            if self.stage is not None:
                raise ValueError("PROFILE_FIELD lineage does not declare a stage")
            return self

        if self.kind == DecisionLineageKind.EVIDENCE_SOURCE:
            if self.stage is not None and self.stage not in DECISION_RESEARCH_STAGES:
                raise ValueError("EVIDENCE_SOURCE lineage may only declare a research stage")
            return self

        if self.kind == DecisionLineageKind.STAGE_RESULT:
            if self.stage not in DECISION_UPSTREAM_STAGES:
                raise ValueError("STAGE_RESULT lineage requires a valid upstream stage")
            return self

        expected_stage = {
            DecisionLineageKind.FINANCIAL_METRIC: AnalysisStage.FINANCE,
            DecisionLineageKind.DECISION_KPI: AnalysisStage.DECISION_ANALYTICS,
            DecisionLineageKind.SENSITIVITY_INPUT: AnalysisStage.DECISION_ANALYTICS,
            DecisionLineageKind.RISK: AnalysisStage.RISK,
            DecisionLineageKind.VALIDATION_ISSUE: AnalysisStage.INDEPENDENT_VALIDATION,
        }[self.kind]
        if self.stage != expected_stage:
            raise ValueError(
                f"{self.kind.value} lineage requires stage {expected_stage.value}"
            )
        return self


class FinalDecisionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: VentureDecision
    confidence: DecisionConfidence
    rationale: str = Field(min_length=10, max_length=3000)
    supporting_evidence_lineage: list[DecisionLineageReference] = Field(
        default_factory=list,
        max_length=50,
    )
    strongest_positive_signals: list[str] = Field(default_factory=list, max_length=20)
    strongest_negative_signals: list[str] = Field(default_factory=list, max_length=20)
    critical_assumptions: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=30)
    what_could_change: list[str] = Field(default_factory=list, max_length=20)
    recommended_next_steps: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("supporting_evidence_lineage", mode="before")
    @classmethod
    def normalize_legacy_lineage(cls, value):
        if value is None:
            return []
        normalized = []
        for item in value:
            if isinstance(item, str):
                try:
                    stage = AnalysisStage(item)
                except ValueError:
                    normalized.append(
                        {
                            "kind": DecisionLineageKind.EVIDENCE_SOURCE.value,
                            "value": item,
                            "stage": None,
                        }
                    )
                else:
                    normalized.append(
                        {
                            "kind": DecisionLineageKind.STAGE_RESULT.value,
                            "value": stage.value,
                            "stage": stage.value,
                        }
                    )
            else:
                normalized.append(item)
        return normalized

    @model_validator(mode="after")
    def validate_unique_lineage(self) -> "FinalDecisionDraft":
        keys = [
            (ref.kind, ref.value, ref.stage)
            for ref in self.supporting_evidence_lineage
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("Decision supporting_evidence_lineage cannot contain duplicates")
        return self


class FinalDecisionAnalysis(FinalDecisionDraft):
    upstream_stage_run_ids: dict[AnalysisStage, UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_upstream_lineage(self) -> "FinalDecisionAnalysis":
        if self.upstream_stage_run_ids:
            if set(self.upstream_stage_run_ids) != DECISION_UPSTREAM_STAGES:
                raise ValueError(
                    "Final Decision upstream_stage_run_ids must contain the complete upstream stage set"
                )
        return self
