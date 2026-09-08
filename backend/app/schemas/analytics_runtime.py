from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.analysis import AnalysisStage
from app.schemas.finance import FinancialScenarioBundle


class AnalyticsStageClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_run_id: UUID
    analysis_run_id: UUID
    stage: AnalysisStage
    attempt: int = Field(ge=1)
    finance_stage_run_id: UUID
    finance_bundle: FinancialScenarioBundle

    @model_validator(mode="after")
    def validate_claim(self) -> "AnalyticsStageClaim":
        if self.stage != AnalysisStage.DECISION_ANALYTICS:
            raise ValueError(
                "AnalyticsStageClaim requires the DECISION_ANALYTICS stage"
            )
        return self
