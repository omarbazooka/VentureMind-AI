from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import FinancialInputName, FinancialMetricName


VALIDATION_RESEARCH_STAGES = frozenset(
    {
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    }
)

VALIDATION_UPSTREAM_STAGES = frozenset(
    {
        *VALIDATION_RESEARCH_STAGES,
        AnalysisStage.BUSINESS_STRATEGY,
        AnalysisStage.FINANCE,
        AnalysisStage.DECISION_ANALYTICS,
        AnalysisStage.RISK,
    }
)


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
    model_config = ConfigDict(extra="forbid")

    category: ValidationIssueCategory
    severity: ValidationSeverity
    description: str = Field(min_length=5, max_length=1000)
    affected_stages: list[AnalysisStage] = Field(default_factory=list, max_length=8)
    profile_fields: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    financial_metrics: list[FinancialMetricName] = Field(default_factory=list, max_length=10)
    decision_kpis: list[DecisionKPIName] = Field(default_factory=list, max_length=10)
    sensitivity_inputs: list[FinancialInputName] = Field(default_factory=list, max_length=10)
    risk_titles: list[str] = Field(default_factory=list, max_length=20)
    suggestion: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_issue_shape(self) -> "ValidationIssue":
        invalid_stages = set(self.affected_stages) - VALIDATION_UPSTREAM_STAGES
        if invalid_stages:
            raise ValueError("Validation issues may only reference upstream analysis stages")

        if self.severity in {ValidationSeverity.HIGH, ValidationSeverity.CRITICAL} and not self.affected_stages:
            raise ValueError("High-severity validation issues require affected stages")

        # Pydantic validates the declared shape only. Whether the declared
        # references are truthful and sufficient is checked deterministically
        # against ValidationAnalysisContext in validation_grounding.py.
        for values, label in (
            (self.affected_stages, "affected_stages"),
            (self.profile_fields, "profile_fields"),
            (self.evidence_ids, "evidence_ids"),
            (self.financial_metrics, "financial_metrics"),
            (self.decision_kpis, "decision_kpis"),
            (self.sensitivity_inputs, "sensitivity_inputs"),
            (self.risk_titles, "risk_titles"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"Validation {label} cannot contain duplicates")

        return self


class ValidationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_assessment: str = Field(min_length=10, max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)


class ValidationAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ValidationStatus
    executive_assessment: str = Field(min_length=10, max_length=2000)
    issues: list[ValidationIssue] = Field(default_factory=list, max_length=30)
    can_proceed: bool
    retry_stages: list[AnalysisStage] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=40)
    upstream_stage_run_ids: dict[AnalysisStage, UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_analysis_consistency(self) -> "ValidationAnalysis":
        if self.status == ValidationStatus.FAILED and self.can_proceed:
            raise ValueError("FAILED validation cannot permit progression")
        if self.status != ValidationStatus.FAILED and not self.can_proceed:
            raise ValueError("Non-failed validation must permit progression")

        if len(self.retry_stages) != len(set(self.retry_stages)):
            raise ValueError("retry_stages cannot contain duplicates")
        if set(self.retry_stages) - VALIDATION_UPSTREAM_STAGES:
            raise ValueError("retry_stages may only reference validation upstream stages")

        if self.upstream_stage_run_ids:
            if set(self.upstream_stage_run_ids) != VALIDATION_UPSTREAM_STAGES:
                raise ValueError(
                    "Validation upstream_stage_run_ids must contain the complete upstream stage set"
                )

        return self
