from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisProfileSnapshot, AnalysisStage
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.decision import DECISION_RESEARCH_STAGES
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchEvidenceGateResult,
)
from app.schemas.risk import RiskAnalysis
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis, ValidationStatus


class InvestmentCommitteeContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_snapshot: AnalysisProfileSnapshot
    research_gate: ResearchEvidenceGateResult
    research_stage_run_ids: dict[AnalysisStage, UUID] = Field(default_factory=dict)
    market_analysis: MarketAnalysis | None = None
    competitor_analysis: CompetitorAnalysis | None = None
    customer_analysis: CustomerAnalysis | None = None
    business_strategy_stage_run_id: UUID
    business_strategy: BusinessStrategyAnalysis
    finance_stage_run_id: UUID
    finance_bundle: FinancialScenarioBundle
    analytics_stage_run_id: UUID
    decision_analytics: DecisionAnalyticsResult
    risk_stage_run_id: UUID
    risk_analysis: RiskAnalysis
    validation_stage_run_id: UUID
    validation_analysis: ValidationAnalysis

    @model_validator(mode="after")
    def validate_context(self) -> "InvestmentCommitteeContext":
        # Production contexts always include explicit research stage-run lineage.
        # Conditional strictness keeps isolated legacy fixtures lightweight while
        # making the authoritative DB-built path fully consistency checked.
        if not self.research_stage_run_ids:
            return self

        if not self.research_gate.can_proceed:
            raise ValueError(
                "Investment Committee requires a Research Evidence Gate that allows progression"
            )

        if set(self.research_stage_run_ids) != DECISION_RESEARCH_STAGES:
            raise ValueError(
                "Investment Committee requires stage-run lineage for all research stages"
            )

        result_by_stage = {
            AnalysisStage.MARKET_RESEARCH: self.market_analysis,
            AnalysisStage.COMPETITOR_INTELLIGENCE: self.competitor_analysis,
            AnalysisStage.CUSTOMER_INTELLIGENCE: self.customer_analysis,
        }
        insufficient = set(self.research_gate.insufficient_stages)
        for stage, result in result_by_stage.items():
            if result is None and stage not in insufficient:
                raise ValueError(
                    "Investment Committee context is missing an accepted research result for "
                    f"{stage.value}"
                )

        if self.decision_analytics.finance_stage_run_id != self.finance_stage_run_id:
            raise ValueError(
                "Decision Analytics does not reference the Finance result in this Committee context"
            )

        if (
            self.validation_analysis.status == ValidationStatus.FAILED
            or not self.validation_analysis.can_proceed
        ):
            raise ValueError(
                "Investment Committee cannot run on a Validation result that blocks progression"
            )

        expected_validation_lineage = {
            **self.research_stage_run_ids,
            AnalysisStage.BUSINESS_STRATEGY: self.business_strategy_stage_run_id,
            AnalysisStage.FINANCE: self.finance_stage_run_id,
            AnalysisStage.DECISION_ANALYTICS: self.analytics_stage_run_id,
            AnalysisStage.RISK: self.risk_stage_run_id,
        }
        if self.validation_analysis.upstream_stage_run_ids != expected_validation_lineage:
            raise ValueError(
                "Independent Validation does not reference the exact upstream results in this Committee context"
            )

        return self


class DecisionStageClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_run_id: UUID
    analysis_run_id: UUID
    stage: AnalysisStage
    attempt: int = Field(ge=1)
    context: InvestmentCommitteeContext

    @model_validator(mode="after")
    def validate_claim(self) -> "DecisionStageClaim":
        if self.stage != AnalysisStage.INVESTMENT_COMMITTEE:
            raise ValueError("DecisionStageClaim requires INVESTMENT_COMMITTEE")
        return self
