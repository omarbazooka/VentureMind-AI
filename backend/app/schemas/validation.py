from enum import StrEnum
from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisStage


class ValidationIssueCategory(StrEnum):
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    CONTRADICTORY_CLAIM = "CONTRADICTORY_CLAIM"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    SENSITIVITY_OVERSIGHT = "SENSITIVITY_OVERSIGHT"
    OVERCONFIDENT_CONCLUSION = "OVERCONFIDENT_CONCLUSION"
    UNREFLECTED_RISK = "UNREFLECTED_RISK"
    FINANCIAL_ANOMALY = "FINANCIAL_ANOMALY"


class ValidationSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ValidationStatus(StrEnum):
    PASSED = "PASSED"
    PASSED_WITH_WARNINGS = "PASSED_WITH_WARNINGS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FAILED = "FAILED"


class ValidationIssue(BaseModel):
    category: ValidationIssueCategory
    severity: ValidationSeverity
    description: str = Field(min_length=5, max_length=1000)
    affected_stages: list[AnalysisStage] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    suggestion: str | None = Field(default=None, max_length=1000)


class ValidationDraft(BaseModel):
    executive_assessment: str = Field(min_length=10, max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ValidationAnalysis(BaseModel):
    status: ValidationStatus
    executive_assessment: str
    issues: list[ValidationIssue] = Field(default_factory=list)
    can_proceed: bool
    retry_stages: list[AnalysisStage] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
