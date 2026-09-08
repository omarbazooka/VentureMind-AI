from decimal import Decimal
from uuid import UUID
from enum import StrEnum
from typing import Literal
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
    FINANCE_RESEARCH_SUPPORT_STAGES,
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

class FinanceUserAnswerMode(StrEnum):
    SELECTED_OPTION = "SELECTED_OPTION"
    CUSTOM = "CUSTOM"

class FinanceInputOptionBasis(StrEnum):
    WEB_EVIDENCE = "WEB_EVIDENCE"
    CALCULATED_FROM_WEB = "CALCULATED_FROM_WEB"


def _validate_known_input_metadata(
    *,
    input_name: FinancialInputName,
    currency: str | None,
    unit_label: str | None,
    period: FinancialPeriod | None,
) -> None:
    if input_name in MONETARY_INPUTS:
        if currency is None:
            raise ValueError(
                "Known monetary Finance "
                "values require currency"
            )
    elif currency is not None:
        raise ValueError(
            "Non-monetary Finance values "
            "cannot declare currency"
        )

    if input_name in UNIT_BASED_INPUTS:
        if not unit_label:
            raise ValueError(
                "Known unit-based Finance "
                "values require unit_label"
            )
    elif unit_label is not None:
        raise ValueError(
            "This Finance input cannot "
            "declare unit_label"
        )

    if input_name in PERIOD_BASED_INPUTS:
        if period is None:
            raise ValueError(
                "Known period-based Finance "
                "values require a period"
            )
    elif period is not None:
        raise ValueError(
            "This Finance input cannot "
            "declare a period"
        )

class FinanceInputOption(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    option_id: str = Field(
        min_length=1,
        max_length=100,
    )

    input_name: FinancialInputName

    label: str = Field(
        min_length=1,
        max_length=300,
    )

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

    basis: FinanceInputOptionBasis

    rationale: str = Field(
        min_length=1,
        max_length=1000,
    )

    supporting_stages: list[
        AnalysisStage
    ] = Field(
        min_length=1,
        max_length=3,
    )

    evidence_source_ids: list[str] = Field(
        min_length=1,
        max_length=20,
    )

    calculation_basis: (
        str | None
    ) = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )

    @field_validator(
        "option_id",
        "label",
        "rationale",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "text cannot be blank"
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
    def validate_option(
        self,
    ) -> "FinanceInputOption":
        _validate_known_input_metadata(
            input_name=self.input_name,
            currency=self.currency,
            unit_label=self.unit_label,
            period=self.period,
        )

        invalid_stages = (
            set(self.supporting_stages)
            - FINANCE_RESEARCH_SUPPORT_STAGES
        )

        if invalid_stages:
            raise ValueError(
                "Finance options may only "
                "reference accepted "
                "research stages"
            )

        if (
            self.basis
            == FinanceInputOptionBasis
            .CALCULATED_FROM_WEB
            and not self.calculation_basis
        ):
            raise ValueError(
                "Calculated market options "
                "require calculation_basis"
            )

        if (
            self.basis
            == FinanceInputOptionBasis
            .WEB_EVIDENCE
            and self.calculation_basis
            is not None
        ):
            raise ValueError(
                "Direct WEB_EVIDENCE options "
                "cannot claim a calculated "
                "basis"
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

    options: list[
        FinanceInputOption
    ] = Field(
        default_factory=list,
        max_length=5,
    )

    allow_custom: Literal[True] = True

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

        option_ids = [
            option.option_id
            for option in self.options
        ]

        if len(option_ids) != len(
            set(option_ids)
        ):
            raise ValueError(
                "Finance input option IDs "
                "must be unique"
            )

        for option in self.options:
            if (
                option.input_name
                != self.input_name
            ):
                raise ValueError(
                    "Finance input options must "
                    "match the requested input"
                )

        if self.options:
            comparison_bases = {
                (
                    option.currency,
                    option.unit_label,
                    option.period,
                )
                for option in self.options
            }

            if len(comparison_bases) != 1:
                raise ValueError(
                    "Finance options must use "
                    "a comparable currency, unit, "
                    "and period basis"
                )

            (
                option_currency,
                option_unit,
                option_period,
            ) = next(
                iter(comparison_bases)
            )

            if (
                self.currency is not None
                and self.currency
                != option_currency
            ):
                raise ValueError(
                    "Request currency must match "
                    "its Finance options"
                )

            if (
                self.unit_label is not None
                and self.unit_label
                != option_unit
            ):
                raise ValueError(
                    "Request unit must match "
                    "its Finance options"
                )

            if (
                self.period is not None
                and self.period
                != option_period
            ):
                raise ValueError(
                    "Request period must match "
                    "its Finance options"
                )

        return self

class FinanceUserInputAnswer(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    input_name: FinancialInputName

    answer_mode: FinanceUserAnswerMode

    selected_option_id: (
        str | None
    ) = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    value: Decimal | None = Field(
        default=None,
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
    def validate_answer(
        self,
    ) -> "FinanceUserInputAnswer":
        if (
            self.answer_mode
            == FinanceUserAnswerMode
            .SELECTED_OPTION
        ):
            if not self.selected_option_id:
                raise ValueError(
                    "Selected-option answers "
                    "require selected_option_id"
                )

            if (
                self.value is not None
                or self.currency is not None
                or self.unit_label is not None
                or self.period is not None
            ):
                raise ValueError(
                    "Selected-option answers "
                    "must not resubmit option "
                    "value metadata"
                )

            return self

        if self.selected_option_id is not None:
            raise ValueError(
                "Custom Finance answers "
                "cannot select an option"
            )

        if self.value is None:
            raise ValueError(
                "Custom Finance answers "
                "require a value"
            )

        _validate_known_input_metadata(
            input_name=self.input_name,
            currency=self.currency,
            unit_label=self.unit_label,
            period=self.period,
        )

        return self