from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.finance import (
    FINANCE_RESEARCH_SUPPORT_STAGES,
    MONETARY_INPUTS,
    PERIOD_BASED_INPUTS,
    UNIT_BASED_INPUTS,
    FinancialAssumptionProvenance,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchEvidenceGateResult,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)


class FinanceAssumptionBuilderContext(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    profile_snapshot: AnalysisProfileSnapshot

    research_gate: ResearchEvidenceGateResult

    market_analysis: MarketAnalysis | None = None

    competitor_analysis: (
        CompetitorAnalysis | None
    ) = None

    customer_analysis: (
        CustomerAnalysis | None
    ) = None

    business_strategy: (
        BusinessStrategyAnalysis
    )

    @model_validator(mode="after")
    def validate_context(
        self,
    ) -> "FinanceAssumptionBuilderContext":
        if not self.research_gate.can_proceed:
            raise ValueError(
                "Finance assumption building "
                "requires a research gate that "
                "allows downstream progression"
            )

        results_by_stage = {
            AnalysisStage.MARKET_RESEARCH: (
                self.market_analysis
            ),
            AnalysisStage
            .COMPETITOR_INTELLIGENCE: (
                self.competitor_analysis
            ),
            AnalysisStage
            .CUSTOMER_INTELLIGENCE: (
                self.customer_analysis
            ),
        }

        insufficient_stages = set(
            self.research_gate
            .insufficient_stages
        )

        for stage, result in (
            results_by_stage.items()
        ):
            if (
                result is None
                and stage
                not in insufficient_stages
            ):
                raise ValueError(
                    "Finance assumption context "
                    "is missing accepted research "
                    f"for {stage.value}"
                )

        return self


class FinancialAssumptionDraft(
    BaseModel
):
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
    def validate_draft(
        self,
    ) -> "FinancialAssumptionDraft":
        has_value = self.value is not None

        invalid_stages = (
            set(self.supporting_stages)
            - FINANCE_RESEARCH_SUPPORT_STAGES
        )

        if invalid_stages:
            raise ValueError(
                "Finance draft may only "
                "reference research stages"
            )

        if not has_value:
            if self.provenance is not None:
                raise ValueError(
                    "Unknown values cannot "
                    "declare provenance"
                )

            if (
                self.profile_fields
                or self.supporting_stages
                or self.evidence_source_ids
            ):
                raise ValueError(
                    "Unknown values cannot "
                    "claim source lineage"
                )

            return self

        if self.provenance is None:
            raise ValueError(
                "Known draft values require "
                "explicit provenance"
            )

        if (
            self.input_name
            in MONETARY_INPUTS
            and self.currency is None
        ):
            raise ValueError(
                "Known monetary values "
                "require currency"
            )

        if (
            self.input_name
            not in MONETARY_INPUTS
            and self.currency is not None
        ):
            raise ValueError(
                "Non-monetary inputs cannot "
                "declare currency"
            )

        if (
            self.input_name
            in UNIT_BASED_INPUTS
            and not self.unit_label
        ):
            raise ValueError(
                "Known unit-based values "
                "require unit_label"
            )

        if (
            self.input_name
            not in UNIT_BASED_INPUTS
            and self.unit_label is not None
        ):
            raise ValueError(
                "This input cannot declare "
                "unit_label"
            )

        if (
            self.input_name
            in PERIOD_BASED_INPUTS
            and self.period is None
        ):
            raise ValueError(
                "Known period-based values "
                "require a period"
            )

        if (
            self.input_name
            not in PERIOD_BASED_INPUTS
            and self.period is not None
        ):
            raise ValueError(
                "This input cannot declare "
                "a period"
            )

        if (
            self.provenance
            == FinancialAssumptionProvenance
            .USER
        ):
            if not self.profile_fields:
                raise ValueError(
                    "USER draft values require "
                    "profile field references"
                )

            if (
                self.supporting_stages
                or self.evidence_source_ids
            ):
                raise ValueError(
                    "USER values cannot claim "
                    "research provenance"
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
                    "WEB values require "
                    "research stages and "
                    "evidence source IDs"
                )

            if self.profile_fields:
                raise ValueError(
                    "WEB values cannot claim "
                    "profile provenance"
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
                    "AI_ASSUMPTION must not "
                    "claim external lineage"
                )

        return self


class FinancialScenarioAssumptionDraft(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    scenario: FinancialScenarioKind

    selling_price_per_unit: (
        FinancialAssumptionDraft
    )

    sales_volume: FinancialAssumptionDraft

    variable_cost_per_unit: (
        FinancialAssumptionDraft
    )

    fixed_costs: FinancialAssumptionDraft

    starting_cash: (
        FinancialAssumptionDraft | None
    ) = None

    @model_validator(mode="after")
    def validate_slots(
        self,
    ) -> (
        "FinancialScenarioAssumptionDraft"
    ):
        expected = {
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

        for field_name, input_name in (
            expected.items()
        ):
            assumption = getattr(
                self,
                field_name,
            )

            if (
                assumption.input_name
                != input_name
            ):
                raise ValueError(
                    f"{field_name} must use "
                    f"{input_name.value}"
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
                "starting_cash draft must "
                "use STARTING_CASH"
            )

        return self


class FinancialAssumptionDraftBundle(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
    )

    base: FinancialScenarioAssumptionDraft

    upside: (
        FinancialScenarioAssumptionDraft
    )

    downside: (
        FinancialScenarioAssumptionDraft
    )

    @model_validator(mode="after")
    def validate_roles(
        self,
    ) -> "FinancialAssumptionDraftBundle":
        if (
            self.base.scenario
            != FinancialScenarioKind.BASE
        ):
            raise ValueError(
                "base draft must use BASE"
            )

        if (
            self.upside.scenario
            != FinancialScenarioKind.UPSIDE
        ):
            raise ValueError(
                "upside draft must use UPSIDE"
            )

        if (
            self.downside.scenario
            != FinancialScenarioKind.DOWNSIDE
        ):
            raise ValueError(
                "downside draft must use "
                "DOWNSIDE"
            )

        return self