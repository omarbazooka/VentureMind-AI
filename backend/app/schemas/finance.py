from decimal import Decimal
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


FINANCE_RESEARCH_SUPPORT_STAGES = (
    frozenset(
        {
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage
            .COMPETITOR_INTELLIGENCE,
            AnalysisStage
            .CUSTOMER_INTELLIGENCE,
        }
    )
)


class FinancialAssumptionProvenance(
    StrEnum
):
    USER = "USER"
    WEB = "WEB"
    AI_ASSUMPTION = "AI_ASSUMPTION"


class FinancialPeriod(StrEnum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class FinancialScenarioKind(StrEnum):
    BASE = "BASE"
    UPSIDE = "UPSIDE"
    DOWNSIDE = "DOWNSIDE"


class FinancialInputName(StrEnum):
    SELLING_PRICE_PER_UNIT = (
        "SELLING_PRICE_PER_UNIT"
    )

    SALES_VOLUME = "SALES_VOLUME"

    VARIABLE_COST_PER_UNIT = (
        "VARIABLE_COST_PER_UNIT"
    )

    FIXED_COSTS = "FIXED_COSTS"

    STARTING_CASH = "STARTING_CASH"


MONETARY_INPUTS = frozenset(
    {
        FinancialInputName
        .SELLING_PRICE_PER_UNIT,

        FinancialInputName
        .VARIABLE_COST_PER_UNIT,

        FinancialInputName.FIXED_COSTS,

        FinancialInputName.STARTING_CASH,
    }
)


UNIT_BASED_INPUTS = frozenset(
    {
        FinancialInputName
        .SELLING_PRICE_PER_UNIT,

        FinancialInputName.SALES_VOLUME,

        FinancialInputName
        .VARIABLE_COST_PER_UNIT,
    }
)


class FinancialAssumption(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    input_name: FinancialInputName

    value: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
    )

    provenance: (
        FinancialAssumptionProvenance
        | None
    ) = None

    currency: str | None = None

    unit_label: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    period: FinancialPeriod | None = None

    rationale: str = Field(
        min_length=1,
        max_length=2000,
    )

    profile_fields: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    supporting_stages: list[
        AnalysisStage
    ] = Field(
        default_factory=list,
        max_length=3,
    )

    evidence_source_ids: list[str] = (
        Field(
            default_factory=list,
            max_length=20,
        )
    )

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

    @model_validator(mode="after")
    def validate_assumption(
        self,
    ) -> "FinancialAssumption":
        has_value = self.value is not None

        if (
            has_value
            and self.provenance is None
        ):
            raise ValueError(
                "Known financial values "
                "must declare provenance"
            )

        if (
            not has_value
            and self.provenance is not None
        ):
            raise ValueError(
                "Unknown financial values "
                "cannot declare provenance"
            )

        if (
            self.input_name
            in MONETARY_INPUTS
        ):
            if self.currency is None:
                raise ValueError(
                    "Monetary financial "
                    "inputs require currency"
                )

        elif self.currency is not None:
            raise ValueError(
                "Non-monetary financial "
                "inputs cannot declare "
                "currency"
            )

        if (
            self.input_name
            in UNIT_BASED_INPUTS
            and not self.unit_label
        ):
            raise ValueError(
                "Unit-based financial "
                "inputs require unit_label"
            )

        if (
            self.input_name
            == FinancialInputName
            .SALES_VOLUME
            and self.period is None
        ):
            raise ValueError(
                "Sales volume requires "
                "a financial period"
            )

        if (
            self.input_name
            == FinancialInputName
            .FIXED_COSTS
            and self.period is None
        ):
            raise ValueError(
                "Fixed costs require "
                "a financial period"
            )

        invalid_stages = (
            set(self.supporting_stages)
            - FINANCE_RESEARCH_SUPPORT_STAGES
        )

        if invalid_stages:
            raise ValueError(
                "Financial assumptions may "
                "only reference research "
                "stages as supporting stages"
            )

        if not has_value:
            if (
                self.profile_fields
                or self.supporting_stages
                or self.evidence_source_ids
            ):
                raise ValueError(
                    "Unknown financial values "
                    "cannot claim source lineage"
                )

            return self

        if (
            self.provenance
            == FinancialAssumptionProvenance
            .USER
        ):
            if not self.profile_fields:
                raise ValueError(
                    "USER financial values "
                    "must reference at least "
                    "one IdeaProfile field"
                )

            if (
                self.supporting_stages
                or self.evidence_source_ids
            ):
                raise ValueError(
                    "USER financial values "
                    "cannot claim research "
                    "provenance"
                )

        elif (
            self.provenance
            == FinancialAssumptionProvenance
            .WEB
        ):
            if (
                not self.supporting_stages
                or not self.evidence_source_ids
            ):
                raise ValueError(
                    "WEB financial values "
                    "must reference research "
                    "stages and evidence "
                    "source IDs"
                )

            if self.profile_fields:
                raise ValueError(
                    "WEB financial values "
                    "cannot claim IdeaProfile "
                    "provenance"
                )

        elif (
            self.provenance
            == FinancialAssumptionProvenance
            .AI_ASSUMPTION
        ):
            if (
                self.profile_fields
                or self.supporting_stages
                or self.evidence_source_ids
            ):
                raise ValueError(
                    "AI_ASSUMPTION values "
                    "must remain explicitly "
                    "unverified"
                )

        return self



class FinancialAssumptionSet(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    scenario: FinancialScenarioKind

    selling_price_per_unit: (
        FinancialAssumption
    )

    sales_volume: FinancialAssumption

    variable_cost_per_unit: (
        FinancialAssumption
    )

    fixed_costs: FinancialAssumption

    starting_cash: (
        FinancialAssumption | None
    ) = None

    @model_validator(mode="after")
    def validate_input_slots(
        self,
    ) -> "FinancialAssumptionSet":
        expected_inputs = {
            "selling_price_per_unit": (
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            "sales_volume": (
                FinancialInputName
                .SALES_VOLUME
            ),
            "variable_cost_per_unit": (
                FinancialInputName
                .VARIABLE_COST_PER_UNIT
            ),
            "fixed_costs": (
                FinancialInputName
                .FIXED_COSTS
            ),
        }

        for (
            field_name,
            expected_name,
        ) in expected_inputs.items():
            assumption = getattr(
                self,
                field_name,
            )

            if (
                assumption.input_name
                != expected_name
            ):
                raise ValueError(
                    f"{field_name} must use "
                    f"{expected_name.value}"
                )

        if (
            self.starting_cash is not None
            and (
                self.starting_cash.input_name
                != FinancialInputName
                .STARTING_CASH
            )
        ):
            raise ValueError(
                "starting_cash must use "
                "STARTING_CASH"
            )

        return self

class FinancialMetricName(StrEnum):
    REVENUE = "REVENUE"

    VARIABLE_COSTS = (
        "VARIABLE_COSTS"
    )

    CONTRIBUTION_PROFIT = (
        "CONTRIBUTION_PROFIT"
    )

    CONTRIBUTION_MARGIN_PERCENT = (
        "CONTRIBUTION_MARGIN_PERCENT"
    )

    OPERATING_RESULT = (
        "OPERATING_RESULT"
    )

    BREAK_EVEN_UNITS = (
        "BREAK_EVEN_UNITS"
    )

    RUNWAY_PERIODS = (
        "RUNWAY_PERIODS"
    )


MONETARY_METRICS = frozenset(
    {
        FinancialMetricName.REVENUE,
        FinancialMetricName
        .VARIABLE_COSTS,
        FinancialMetricName
        .CONTRIBUTION_PROFIT,
        FinancialMetricName
        .OPERATING_RESULT,
    }
)


class CalculatedFinancialMetric(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    metric_name: FinancialMetricName

    value: Decimal

    currency: str | None = None

    unit: str = Field(
        min_length=1,
        max_length=100,
    )

    formula: str = Field(
        min_length=1,
        max_length=1000,
    )

    input_names: list[
        FinancialInputName
    ] = Field(
        min_length=1,
        max_length=10,
    )

    provenance: Literal[
        "CALCULATED"
    ] = "CALCULATED"

    @field_validator("currency")
    @classmethod
    def normalize_metric_currency(
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

    @model_validator(mode="after")
    def validate_metric(
        self,
    ) -> "CalculatedFinancialMetric":
        if (
            self.metric_name
            in MONETARY_METRICS
            and self.currency is None
        ):
            raise ValueError(
                "Monetary calculated "
                "metrics require currency"
            )

        if (
            self.metric_name
            not in MONETARY_METRICS
            and self.currency is not None
        ):
            raise ValueError(
                "Non-monetary calculated "
                "metrics cannot declare "
                "currency"
            )

        return self

class FinancialScenarioResult(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    scenario: FinancialScenarioKind

    assumptions: FinancialAssumptionSet

    metrics: list[
        CalculatedFinancialMetric
    ] = Field(
        default_factory=list,
        max_length=20,
    )

    missing_critical_inputs: list[
        FinancialInputName
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_scenario(
        self,
    ) -> "FinancialScenarioResult":
        if (
            self.scenario
            != self.assumptions.scenario
        ):
            raise ValueError(
                "Scenario result and "
                "assumption set must match"
            )

        metric_names = [
            metric.metric_name
            for metric in self.metrics
        ]

        if (
            len(metric_names)
            != len(set(metric_names))
        ):
            raise ValueError(
                "Financial scenario cannot "
                "contain duplicate metrics"
            )

        return self

class FinanceReadinessStatus(
    StrEnum
):
    READY_FOR_CALCULATION = (
        "READY_FOR_CALCULATION"
    )

    MISSING_CRITICAL_INPUTS = (
        "MISSING_CRITICAL_INPUTS"
    )

    INCOMPATIBLE_INPUTS = (
        "INCOMPATIBLE_INPUTS"
    )


class FinanceReadinessIssueCode(
    StrEnum
):
    CORE_CURRENCY_MISMATCH = (
        "CORE_CURRENCY_MISMATCH"
    )

    CORE_UNIT_MISMATCH = (
        "CORE_UNIT_MISMATCH"
    )

    STARTING_CASH_MISSING = (
        "STARTING_CASH_MISSING"
    )

    STARTING_CASH_CURRENCY_MISMATCH = (
        "STARTING_CASH_CURRENCY_MISMATCH"
    )


class FinanceReadinessResult(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    scenario: FinancialScenarioKind

    status: FinanceReadinessStatus

    can_calculate_core: bool

    missing_critical_inputs: list[
        FinancialInputName
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    blocking_issues: list[
        FinanceReadinessIssueCode
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    optional_issues: list[
        FinanceReadinessIssueCode
    ] = Field(
        default_factory=list,
        max_length=10,
    )

    runway_input_ready: bool = False

    @model_validator(mode="after")
    def validate_readiness_result(
        self,
    ) -> "FinanceReadinessResult":
        if (
            self.status
            == FinanceReadinessStatus
            .READY_FOR_CALCULATION
            and not self.can_calculate_core
        ):
            raise ValueError(
                "READY_FOR_CALCULATION "
                "requires "
                "can_calculate_core=True"
            )

        if (
            self.status
            != FinanceReadinessStatus
            .READY_FOR_CALCULATION
            and self.can_calculate_core
        ):
            raise ValueError(
                "Non-ready Finance status "
                "cannot allow core calculation"
            )

        if (
            self.status
            == FinanceReadinessStatus
            .MISSING_CRITICAL_INPUTS
            and not (
                self.missing_critical_inputs
            )
        ):
            raise ValueError(
                "MISSING_CRITICAL_INPUTS "
                "requires explicit missing "
                "inputs"
            )

        if (
            self.status
            == FinanceReadinessStatus
            .INCOMPATIBLE_INPUTS
            and not self.blocking_issues
        ):
            raise ValueError(
                "INCOMPATIBLE_INPUTS "
                "requires blocking issues"
            )

        if (
            self.runway_input_ready
            and not self.can_calculate_core
        ):
            raise ValueError(
                "Runway inputs cannot be "
                "ready while core Finance "
                "is not ready"
            )

        return self