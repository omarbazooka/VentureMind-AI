from enum import StrEnum
from pydantic import BaseModel, Field


class VentureDecision(StrEnum):
    GO = "GO"
    CONDITIONAL_GO = "CONDITIONAL_GO"
    NO_GO = "NO_GO"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DecisionConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FinalDecisionDraft(BaseModel):
    decision: VentureDecision
    confidence: DecisionConfidence
    rationale: str = Field(min_length=10, max_length=3000)
    supporting_evidence_lineage: list[str] = Field(default_factory=list)
    strongest_positive_signals: list[str] = Field(default_factory=list)
    strongest_negative_signals: list[str] = Field(default_factory=list)
    critical_assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    what_could_change: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class FinalDecisionAnalysis(BaseModel):
    decision: VentureDecision
    confidence: DecisionConfidence
    rationale: str
    supporting_evidence_lineage: list[str] = Field(default_factory=list)
    strongest_positive_signals: list[str] = Field(default_factory=list)
    strongest_negative_signals: list[str] = Field(default_factory=list)
    critical_assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    what_could_change: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
