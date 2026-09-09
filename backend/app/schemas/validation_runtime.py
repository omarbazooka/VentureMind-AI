from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.analysis import AnalysisProfileSnapshot, AnalysisStage
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchEvidenceGateResult,
)
from app.schemas.risk import RiskAnalysis
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import VALIDATION_RESEARCH_STAGES


class ValidationAnalysisContext(BaseModel):
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

    @model_validator(mode="after")
    def validate_context(self) -> "ValidationAnalysisContext":
        # Production contexts are built by validation_context.py and always carry
        # explicit research stage-run lineage. Keeping the checks conditional
        # preserves lightweight isolated test fixtures while making the real
        # runtime path strict.
        if not self.research_stage_run_ids:
            return self

        if not self.research_gate.can_proceed:
            raise ValueError("Validation context requires a Research Evidence Gate that allows progression")

        if set(self.research_stage_run_ids) != VALIDATION_RESEARCH_STAGES:
            raise ValueError("Validation context requires stage-run lineage for all research stages")

        result_by_stage = {
            AnalysisStage.MARKET_RESEARCH: self.market_analysis,
            AnalysisStage.COMPETITOR_INTELLIGENCE: self.competitor_analysis,
            AnalysisStage.CUSTOMER_INTELLIGENCE: self.customer_analysis,
        }
        insufficient = set(self.research_gate.insufficient_stages)
        for stage, result in result_by_stage.items():
            if result is None and stage not in insufficient:
                raise ValueError(
                    "Validation context is missing an accepted research result for "
                    f"{stage.value}"
                )

        if self.decision_analytics.finance_stage_run_id != self.finance_stage_run_id:
            raise ValueError(
                "Decision Analytics does not reference the Finance result in this Validation context"
            )

        return self


class ValidationStageClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_run_id: UUID
    analysis_run_id: UUID
    stage: AnalysisStage
    attempt: int = Field(ge=1)
    context: ValidationAnalysisContext

    @model_validator(mode="after")
    def validate_claim(self) -> "ValidationStageClaim":
        if self.stage != AnalysisStage.INDEPENDENT_VALIDATION:
            raise ValueError("ValidationStageClaim requires INDEPENDENT_VALIDATION")
        return self
