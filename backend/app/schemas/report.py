from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision import FinalDecisionAnalysis
from app.schemas.validation import ValidationAnalysis


class ReportMetricStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ReportMetricValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReportMetricStatus
    value: str | None = None
    unit: str | None = None
    explanation: str | None = None


class ReportMarketMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tam: ReportMetricValue = Field(
        default_factory=lambda: ReportMetricValue(
            status=ReportMetricStatus.UNAVAILABLE,
            explanation="Evidence does not support TAM calculation",
        )
    )
    sam: ReportMetricValue = Field(
        default_factory=lambda: ReportMetricValue(
            status=ReportMetricStatus.UNAVAILABLE,
            explanation="Evidence does not support SAM calculation",
        )
    )
    som: ReportMetricValue = Field(
        default_factory=lambda: ReportMetricValue(
            status=ReportMetricStatus.UNAVAILABLE,
            explanation="Evidence does not support SOM calculation",
        )
    )
    cagr: ReportMetricValue = Field(
        default_factory=lambda: ReportMetricValue(
            status=ReportMetricStatus.UNAVAILABLE,
            explanation="Evidence does not support CAGR calculation",
        )
    )
    willingness_to_pay: ReportMetricValue = Field(
        default_factory=lambda: ReportMetricValue(
            status=ReportMetricStatus.UNAVAILABLE,
            explanation="Evidence does not support willingness-to-pay estimation",
        )
    )


class ReportMarketSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    evidence_quality: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    market_metrics: ReportMarketMetrics = Field(
        default_factory=ReportMarketMetrics
    )
    limitations: list[str] = Field(default_factory=list)


class ReportCompetitorSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    evidence_quality: str
    competitors: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportCustomerSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    evidence_quality: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportStrategySection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    positioning: list[dict[str, Any]] = Field(default_factory=list)
    value_proposition: list[dict[str, Any]] = Field(default_factory=list)
    business_model_implications: list[dict[str, Any]] = Field(
        default_factory=list
    )
    go_to_market: list[dict[str, Any]] = Field(default_factory=list)
    strategic_strengths: list[dict[str, Any]] = Field(default_factory=list)
    strategic_weaknesses: list[dict[str, Any]] = Field(default_factory=list)
    critical_assumptions: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportFinanceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    base_scenario: dict[str, Any]
    upside_scenario: dict[str, Any]
    downside_scenario: dict[str, Any]
    comparisons: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportAnalyticsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpis: list[dict[str, Any]] = Field(default_factory=list)
    scenario_relative_changes: list[dict[str, Any]] = Field(
        default_factory=list
    )
    sensitivity: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)


class ReportRiskSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str
    overall_level: str | None = None
    risks: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportValidationSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    executive_assessment: str
    issues: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ReportChartData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    break_even_comparison: list[dict[str, Any]] = Field(default_factory=list)
    monthly_projections: list[dict[str, Any]] = Field(default_factory=list)
    sensitivity_ranking: list[dict[str, Any]] = Field(default_factory=list)
    risk_matrix: list[dict[str, Any]] = Field(default_factory=list)


class ReportSourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    title: str
    url: str | None = None
    provenance: str
    stage: str


class StructuredReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    idea_id: UUID
    analysis_run_id: UUID
    version: int = Field(ge=1)
    title: str
    executive_summary: str
    decision: FinalDecisionAnalysis
    profile_summary: dict[str, Any]
    market: ReportMarketSection
    competitors: ReportCompetitorSection
    customer: ReportCustomerSection
    strategy: ReportStrategySection
    finance: ReportFinanceSection
    analytics: ReportAnalyticsSection
    risk: ReportRiskSection
    validation: ReportValidationSection
    chart_data: ReportChartData
    sources: list[ReportSourceItem] = Field(default_factory=list)
    created_at: datetime
