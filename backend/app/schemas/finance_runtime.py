from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.finance import (
    MONETARY_INPUTS,
    PERIOD_BASED_INPUTS,
    UNIT_BASED_INPUTS,
    FinancialInputName,
    FinancialPeriod,
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

class FinanceInputRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    input_name: FinancialInputName

    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    currency: str | None = None

    unit_label: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    period: FinancialPeriod | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "question cannot be blank"
            )

        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip().upper()

        if (
            len(normalized) != 3
            or not normalized.isalpha()
        ):
            raise ValueError(
                "currency must be a "
                "3-letter code"
            )

        return normalized

    @field_validator("unit_label")
    @classmethod
    def normalize_unit_label(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "unit_label cannot be blank"
            )

        return normalized

    @model_validator(mode="after")
    def validate_request_metadata(
        self,
    ) -> "FinanceInputRequest":
        if (
            self.input_name
            not in MONETARY_INPUTS
            and self.currency is not None
        ):
            raise ValueError(
                "Non-monetary Finance "
                "input requests cannot "
                "declare currency"
            )

        if (
            self.input_name
            not in UNIT_BASED_INPUTS
            and self.unit_label is not None
        ):
            raise ValueError(
                "This Finance input request "
                "cannot declare unit_label"
            )

        if (
            self.input_name
            not in PERIOD_BASED_INPUTS
            and self.period is not None
        ):
            raise ValueError(
                "This Finance input request "
                "cannot declare a period"
            )

        return self

class FinanceUserInputAnswer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    input_name: FinancialInputName

    value: Decimal = Field(
        ge=Decimal("0"),
    )

    currency: str | None = None

    unit_label: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    period: FinancialPeriod | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip().upper()

        if (
            len(normalized) != 3
            or not normalized.isalpha()
        ):
            raise ValueError(
                "currency must be a "
                "3-letter code"
            )

        return normalized

    @field_validator("unit_label")
    @classmethod
    def normalize_unit_label(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "unit_label cannot be blank"
            )

        return normalized

    @model_validator(mode="after")
    def validate_answer_metadata(
        self,
    ) -> "FinanceUserInputAnswer":
        if self.input_name in MONETARY_INPUTS:
            if self.currency is None:
                raise ValueError(
                    "Known monetary Finance "
                    "answers require currency"
                )

        elif self.currency is not None:
            raise ValueError(
                "Non-monetary Finance "
                "answers cannot declare "
                "currency"
            )

        if self.input_name in UNIT_BASED_INPUTS:
            if not self.unit_label:
                raise ValueError(
                    "Known unit-based Finance "
                    "answers require unit_label"
                )

        elif self.unit_label is not None:
            raise ValueError(
                "This Finance answer cannot "
                "declare unit_label"
            )

        if self.input_name in PERIOD_BASED_INPUTS:
            if self.period is None:
                raise ValueError(
                    "Known period-based Finance "
                    "answers require a period"
                )

        elif self.period is not None:
            raise ValueError(
                "This Finance answer cannot "
                "declare a period"
            )

        return self