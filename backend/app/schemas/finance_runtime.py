from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
)


class FinanceStageClaim(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    stage_run_id: UUID
    analysis_run_id: UUID

    stage: AnalysisStage

    attempt: int = Field(
        ge=1,
    )

    assumption_context: (
        FinanceAssumptionBuilderContext
    )

    @model_validator(mode="after")
    def validate_finance_claim(
        self,
    ) -> "FinanceStageClaim":
        if (
            self.stage
            != AnalysisStage.FINANCE
        ):
            raise ValueError(
                "FinanceStageClaim requires "
                "the FINANCE stage"
            )

        return self