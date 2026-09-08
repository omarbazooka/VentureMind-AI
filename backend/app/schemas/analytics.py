from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.finance import (
    MONETARY_METRICS,
    PERIOD_BASED_METRICS,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioKind,
)


SENSITIVITY_INPUTS = frozenset(
    {
        FinancialInputName.SELLING_PRICE_PER_UNIT,
        FinancialInputName.SALES_VOLUME,
        FinancialInputName.VARIABLE_COST_PER_UNIT,
        FinancialInputName.FIXED_COSTS,
    }
)


class DecisionKPIName(StrEnum):
    OPERATING_MARGIN_PERCENT = "OPERATING_MARGIN_PERCENT"
    BREAK_EVEN_HEADROOM_PERCENT = "BREAK_EVEN_HEADROOM_PERCENT"


class DecisionKPI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: DecisionKPIName
    scenario: FinancialScenarioKind
    value: Decimal
    unit: Literal["percent"] = "percent"
    formula: str = Field(min_length=1, max_length=1000)
    source_financial_metrics: list[FinancialMetricName] = Field(
        default_factory=list,
        max_length=10,
    )
    source_financial_inputs: list[FinancialInputName] = Field(
        default_factory=list,
        max_length=10,
    )
    provenance: Literal["CALCULATED"] = "CALCULATED"

    @model_validator(mode="after")
    def validate_kpi_lineage(self) -> "DecisionKPI":
        metric_sources = set(self.source_financial_metrics)
        input_sources = set(self.source_financial_inputs)

        if self.metric_name == DecisionKPIName.OPERATING_MARGIN_PERCENT:
            required_metrics = {
                FinancialMetricName.REVENUE,
                FinancialMetricName.OPERATING_RESULT,
            }
            if not required_metrics.issubset(metric_sources):
                raise ValueError(
                    "OPERATING_MARGIN_PERCENT requires REVENUE and "
                    "OPERATING_RESULT source metrics"
                )

        elif self.metric_name == DecisionKPIName.BREAK_EVEN_HEADROOM_PERCENT:
            if FinancialMetricName.BREAK_EVEN_UNITS not in metric_sources:
                raise ValueError(
                    "BREAK_EVEN_HEADROOM_PERCENT requires "
                    "BREAK_EVEN_UNITS as a source metric"
                )
            if FinancialInputName.SALES_VOLUME not in input_sources:
                raise ValueError(
                    "BREAK_EVEN_HEADROOM_PERCENT requires SALES_VOLUME "
                    "as a source financial input"
                )

        return self


class ScenarioRelativeChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: FinancialMetricName
    upside_relative_change_percent: Decimal | None = None
    downside_relative_change_percent: Decimal | None = None
    provenance: Literal["CALCULATED"] = "CALCULATED"


class SensitivityMetricImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: FinancialMetricName
    base_value: Decimal
    stressed_value: Decimal
    absolute_change: Decimal
    relative_change_percent: Decimal | None = None
    currency: str | None = None
    unit: str = Field(min_length=1, max_length=100)
    period: FinancialPeriod | None = None
    provenance: Literal["CALCULATED"] = "CALCULATED"

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a 3-letter code")
        return normalized

    @model_validator(mode="after")
    def validate_impact(self) -> "SensitivityMetricImpact":
        if self.absolute_change != self.stressed_value - self.base_value:
            raise ValueError(
                "Sensitivity absolute_change must equal stressed_value - base_value"
            )

        if self.base_value == 0 and self.relative_change_percent is not None:
            raise ValueError(
                "Sensitivity relative change is undefined when base_value is zero"
            )

        if self.base_value != 0 and self.relative_change_percent is None:
            raise ValueError(
                "Sensitivity relative change is required when base_value is non-zero"
            )

        if self.metric_name in MONETARY_METRICS:
            if self.currency is None:
                raise ValueError(
                    "Monetary sensitivity impacts require currency"
                )
        elif self.currency is not None:
            raise ValueError(
                "Non-monetary sensitivity impacts cannot declare currency"
            )

        if self.metric_name in PERIOD_BASED_METRICS:
            if self.period is None:
                raise ValueError(
                    "Period-based sensitivity impacts require a period"
                )
        elif self.period is not None:
            raise ValueError(
                "This sensitivity metric cannot declare a period"
            )

        return self


class SensitivityPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_name: FinancialInputName
    input_change_percent: Decimal = Field(ge=Decimal("-100"))
    impacts: list[SensitivityMetricImpact] = Field(
        min_length=1,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_point(self) -> "SensitivityPoint":
        if self.input_name not in SENSITIVITY_INPUTS:
            raise ValueError(
                "Sensitivity analysis only supports core operating inputs"
            )

        metric_names = [impact.metric_name for impact in self.impacts]
        if len(metric_names) != len(set(metric_names)):
            raise ValueError(
                "Sensitivity point cannot contain duplicate metric impacts"
            )

        return self


class InputSensitivityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_name: FinancialInputName
    decrease: SensitivityPoint
    increase: SensitivityPoint
    max_abs_ranking_metric_change_percent: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
    )
    rank: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_input_sensitivity(self) -> "InputSensitivityResult":
        if self.input_name not in SENSITIVITY_INPUTS:
            raise ValueError(
                "Sensitivity analysis only supports core operating inputs"
            )

        if (
            self.decrease.input_name != self.input_name
            or self.increase.input_name != self.input_name
        ):
            raise ValueError(
                "Sensitivity points must match the parent financial input"
            )

        if self.decrease.input_change_percent >= 0:
            raise ValueError(
                "Decrease sensitivity point must use a negative percentage change"
            )

        if self.increase.input_change_percent <= 0:
            raise ValueError(
                "Increase sensitivity point must use a positive percentage change"
            )

        return self


class SensitivityAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shock_percent: Decimal = Field(gt=Decimal("0"), le=Decimal("100"))
    ranking_metric: FinancialMetricName
    inputs: list[InputSensitivityResult] = Field(
        default_factory=list,
        max_length=10,
    )
    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_sensitivity_analysis(self) -> "SensitivityAnalysisResult":
        input_names = [item.input_name for item in self.inputs]
        if len(input_names) != len(set(input_names)):
            raise ValueError(
                "Sensitivity analysis cannot contain duplicate input results"
            )

        expected_decrease = -self.shock_percent
        expected_increase = self.shock_percent
        for item in self.inputs:
            if item.decrease.input_change_percent != expected_decrease:
                raise ValueError(
                    "Sensitivity decrease point must match shock_percent"
                )
            if item.increase.input_change_percent != expected_increase:
                raise ValueError(
                    "Sensitivity increase point must match shock_percent"
                )

            for point in (item.decrease, item.increase):
                impact_metrics = {impact.metric_name for impact in point.impacts}
                if self.ranking_metric not in impact_metrics:
                    raise ValueError(
                        "Every sensitivity point must include the ranking metric"
                    )

        return self


class DecisionAnalyticsResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finance_stage_run_id: UUID
    kpis: list[DecisionKPI] = Field(
        default_factory=list,
        max_length=30,
    )
    scenario_relative_changes: list[ScenarioRelativeChange] = Field(
        default_factory=list,
        max_length=20,
    )
    sensitivity: SensitivityAnalysisResult | None = None
    limitations: list[str] = Field(
        default_factory=list,
        max_length=30,
    )

    @model_validator(mode="after")
    def validate_result(self) -> "DecisionAnalyticsResult":
        kpi_keys = [
            (kpi.metric_name, kpi.scenario)
            for kpi in self.kpis
        ]
        if len(kpi_keys) != len(set(kpi_keys)):
            raise ValueError(
                "Decision Analytics cannot contain duplicate KPI/scenario pairs"
            )

        comparison_metrics = [
            item.metric_name
            for item in self.scenario_relative_changes
        ]
        if len(comparison_metrics) != len(set(comparison_metrics)):
            raise ValueError(
                "Decision Analytics cannot contain duplicate scenario comparisons"
            )

        return self
