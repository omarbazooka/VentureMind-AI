from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
from app.schemas.validation import ValidationAnalysis


class InvestmentCommitteeContext(BaseModel):
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
    risk_stage_run_id: UUID
    risk_analysis: RiskAnalysis
    validation_stage_run_id: UUID
    validation_analysis: ValidationAnalysis


class DecisionStageClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_run_id: UUID
    analysis_run_id: UUID
    stage: AnalysisStage
    attempt: int
    context: InvestmentCommitteeContext
