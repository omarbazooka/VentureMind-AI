from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchEvidenceGateResult,
)
from app.schemas.strategy import BusinessStrategyAnalysis


class RiskAnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_snapshot: AnalysisProfileSnapshot
    research_gate: ResearchEvidenceGateResult
    market_analysis: MarketAnalysis | None = None
    competitor_analysis: CompetitorAnalysis | None = None
    customer_analysis: CustomerAnalysis | None = None
    business_strategy_stage_run_id: UUID
    business_strategy: BusinessStrategyAnalysis
    finance_stage_run_id: UUID
    finance_bundle: FinancialScenarioBundle
    analytics_stage_run_id: UUID
    decision_analytics: DecisionAnalyticsResult

    @model_validator(mode="after")
    def validate_context(self) -> "RiskAnalysisContext":
        if not self.research_gate.can_proceed:
            raise ValueError(
                "Risk context requires a Research Evidence Gate that allows progression"
            )

        result_by_stage = {
            AnalysisStage.MARKET_RESEARCH: self.market_analysis,
            AnalysisStage.COMPETITOR_INTELLIGENCE: self.competitor_analysis,
            AnalysisStage.CUSTOMER_INTELLIGENCE: self.customer_analysis,
        }
        insufficient = set(
            self.research_gate.insufficient_stages
        )
        for stage, result in result_by_stage.items():
            if result is None and stage not in insufficient:
                raise ValueError(
                    "Risk context is missing an accepted research result for "
                    f"{stage.value}"
                )

        if (
            self.decision_analytics.finance_stage_run_id
            != self.finance_stage_run_id
        ):
            raise ValueError(
                "Decision Analytics does not reference the Finance result in this Risk context"
            )

        return self
