import re
from decimal import Decimal, InvalidOperation

from app.schemas.analysis import AnalysisStage
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
)
from app.schemas.finance_runtime import (
    FinanceInputOption,
    FinanceInputOptionBasis,
    FinanceInputRequest,
)
from app.schemas.research import (
    CompetitorFindingCategory,
    EvidenceProvenance,
    ResearchClaimKind,
)


_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?"
)


_QUESTIONS = {
    FinancialInputName.SELLING_PRICE_PER_UNIT: (
        "Which selling price should we use "
        "for the financial model?"
    ),
    FinancialInputName.SALES_VOLUME: (
        "What sales volume should we use "
        "for the financial model?"
    ),
    FinancialInputName.VARIABLE_COST_PER_UNIT: (
        "What variable cost per unit should "
        "we use for the financial model?"
    ),
    FinancialInputName.FIXED_COSTS: (
        "What fixed costs should we use for "
        "the financial model?"
    ),
    FinancialInputName.STARTING_CASH: (
        "How much starting cash should we use "
        "for the financial model?"
    ),
}


def _decimal_values(
    statement: str,
) -> set[Decimal]:
    values: set[Decimal] = set()

    for match in _NUMERIC_TOKEN_PATTERN.findall(
        statement
    ):
        normalized = match.replace(",", "")
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            continue

        if value >= 0:
            values.add(value)

    return values


def _assumption_for_input(
    *,
    assumptions: FinancialAssumptionSet,
    input_name: FinancialInputName,
) -> FinancialAssumption | None:
    if (
        input_name
        == FinancialInputName.SELLING_PRICE_PER_UNIT
    ):
        return assumptions.selling_price_per_unit
    if input_name == FinancialInputName.SALES_VOLUME:
        return assumptions.sales_volume
    if (
        input_name
        == FinancialInputName.VARIABLE_COST_PER_UNIT
    ):
        return assumptions.variable_cost_per_unit
    if input_name == FinancialInputName.FIXED_COSTS:
        return assumptions.fixed_costs
    if input_name == FinancialInputName.STARTING_CASH:
        return assumptions.starting_cash

    return None


def _accepted_web_source_ids(
    context: FinanceAssumptionBuilderContext,
) -> set[str]:
    analysis = context.competitor_analysis

    if analysis is None:
        return set()

    return {
        source.source_id
        for source in analysis.evidence_sources
        if source.provenance == EvidenceProvenance.WEB
    }


def _statement_matches_basis(
    *,
    statement: str,
    currency: str,
    unit_label: str,
) -> bool:
    normalized = statement.casefold()

    return (
        currency.casefold() in normalized
        and unit_label.casefold() in normalized
    )


def _collect_competitor_price_points(
    *,
    context: FinanceAssumptionBuilderContext,
    currency: str,
    unit_label: str,
) -> dict[Decimal, set[str]]:
    if (
        AnalysisStage.COMPETITOR_INTELLIGENCE
        in context.research_gate.insufficient_stages
    ):
        return {}

    analysis = context.competitor_analysis
    if analysis is None:
        return {}

    allowed_source_ids = _accepted_web_source_ids(
        context
    )
    points: dict[Decimal, set[str]] = {}

    def add_statement(
        *,
        statement: str,
        claim_kind: ResearchClaimKind,
        is_numerical: bool,
        source_ids: list[str],
    ) -> None:
        if (
            claim_kind != ResearchClaimKind.OBSERVED
            or not is_numerical
        ):
            return

        cited = set(source_ids) & allowed_source_ids
        if not cited:
            return

        if not _statement_matches_basis(
            statement=statement,
            currency=currency,
            unit_label=unit_label,
        ):
            return

        for value in _decimal_values(statement):
            points.setdefault(
                value,
                set(),
            ).update(cited)

    for competitor in analysis.competitors:
        pricing = competitor.pricing
        if pricing is None:
            continue

        add_statement(
            statement=pricing.statement,
            claim_kind=pricing.claim_kind,
            is_numerical=pricing.is_numerical,
            source_ids=pricing.evidence_source_ids,
        )

    for finding in analysis.findings:
        if (
            finding.category
            != CompetitorFindingCategory.PRICING
        ):
            continue

        add_statement(
            statement=finding.statement,
            claim_kind=finding.claim_kind,
            is_numerical=finding.is_numerical,
            source_ids=finding.evidence_source_ids,
        )

    return points


def _selling_price_options(
    *,
    assumptions: FinancialAssumptionSet,
    context: FinanceAssumptionBuilderContext,
) -> list[FinanceInputOption]:
    assumption = assumptions.selling_price_per_unit

    if (
        assumption.currency is None
        or assumption.unit_label is None
    ):
        return []

    points = _collect_competitor_price_points(
        context=context,
        currency=assumption.currency,
        unit_label=assumption.unit_label,
    )

    if not points:
        return []

    values = sorted(points)
    low = values[0]
    high = values[-1]

    options: list[FinanceInputOption] = []

    options.append(
        FinanceInputOption(
            option_id="market_low",
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            label="Lower observed market benchmark",
            value=low,
            currency=assumption.currency,
            unit_label=assumption.unit_label,
            basis=FinanceInputOptionBasis.WEB_EVIDENCE,
            rationale=(
                "Lowest directly observed competitor "
                "price on the same validated basis."
            ),
            supporting_stages=[
                AnalysisStage.COMPETITOR_INTELLIGENCE
            ],
            evidence_source_ids=sorted(
                points[low]
            ),
        )
    )

    if high != low:
        midpoint = (
            low + high
        ) / Decimal("2")
        all_source_ids = sorted(
            {
                source_id
                for source_ids in points.values()
                for source_id in source_ids
            }
        )

        if midpoint not in {low, high}:
            options.append(
                FinanceInputOption(
                    option_id="market_midpoint",
                    input_name=(
                        FinancialInputName
                        .SELLING_PRICE_PER_UNIT
                    ),
                    label="Market midpoint",
                    value=midpoint,
                    currency=assumption.currency,
                    unit_label=assumption.unit_label,
                    basis=(
                        FinanceInputOptionBasis
                        .CALCULATED_FROM_WEB
                    ),
                    rationale=(
                        "Deterministic midpoint between "
                        "the lower and upper accepted "
                        "competitor price benchmarks."
                    ),
                    supporting_stages=[
                        AnalysisStage
                        .COMPETITOR_INTELLIGENCE
                    ],
                    evidence_source_ids=all_source_ids,
                    calculation_basis=(
                        "(lowest accepted observed price "
                        "+ highest accepted observed "
                        "price) / 2"
                    ),
                )
            )

        options.append(
            FinanceInputOption(
                option_id="market_high",
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                label="Upper observed market benchmark",
                value=high,
                currency=assumption.currency,
                unit_label=assumption.unit_label,
                basis=(
                    FinanceInputOptionBasis.WEB_EVIDENCE
                ),
                rationale=(
                    "Highest directly observed competitor "
                    "price on the same validated basis."
                ),
                supporting_stages=[
                    AnalysisStage.COMPETITOR_INTELLIGENCE
                ],
                evidence_source_ids=sorted(
                    points[high]
                ),
            )
        )

    return options


def build_finance_input_request(
    *,
    input_name: FinancialInputName,
    assumptions: FinancialAssumptionSet,
    context: FinanceAssumptionBuilderContext,
) -> FinanceInputRequest:
    assumption = _assumption_for_input(
        assumptions=assumptions,
        input_name=input_name,
    )

    currency = (
        assumption.currency
        if assumption is not None
        else None
    )
    unit_label = (
        assumption.unit_label
        if assumption is not None
        else None
    )
    period = (
        assumption.period
        if assumption is not None
        else None
    )

    options: list[FinanceInputOption] = []

    if (
        input_name
        == FinancialInputName.SELLING_PRICE_PER_UNIT
    ):
        options = _selling_price_options(
            assumptions=assumptions,
            context=context,
        )

    return FinanceInputRequest(
        input_name=input_name,
        question=_QUESTIONS[input_name],
        options=options,
        currency=currency,
        unit_label=unit_label,
        period=period,
    )
