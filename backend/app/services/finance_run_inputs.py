from collections.abc import Sequence
from uuid import UUID

from pydantic import ValidationError

from app.models.analysis_run_input import (
    AnalysisRunInput,
)
from app.schemas.analysis import (
    AnalysisRunInputStatus,
)
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialScenarioInputs,
)
from app.schemas.finance_runtime import (
    ResolvedFinanceUserInput,
)


class FinanceRunInputGroundingError(
    RuntimeError
):
    pass


_INPUT_FIELDS = {
    FinancialInputName.SELLING_PRICE_PER_UNIT: (
        "selling_price_per_unit"
    ),
    FinancialInputName.SALES_VOLUME: (
        "sales_volume"
    ),
    FinancialInputName.VARIABLE_COST_PER_UNIT: (
        "variable_cost_per_unit"
    ),
    FinancialInputName.FIXED_COSTS: (
        "fixed_costs"
    ),
    FinancialInputName.STARTING_CASH: (
        "starting_cash"
    ),
}


def _resolve_persisted_input(
    *,
    run_input: AnalysisRunInput,
    analysis_run_id: UUID,
    stage_run_id: UUID,
) -> ResolvedFinanceUserInput:
    if run_input.analysis_run_id != analysis_run_id:
        raise FinanceRunInputGroundingError(
            "Finance run input belongs to a "
            "different AnalysisRun"
        )

    if run_input.stage_run_id != stage_run_id:
        raise FinanceRunInputGroundingError(
            "Finance run input belongs to a "
            "different stage run"
        )

    if (
        run_input.status
        != AnalysisRunInputStatus.ANSWERED.value
    ):
        raise FinanceRunInputGroundingError(
            "Only ANSWERED Finance run inputs "
            "may become authoritative inputs"
        )

    if run_input.response_data is None:
        raise FinanceRunInputGroundingError(
            "Answered Finance run input has no "
            "persisted response_data"
        )

    try:
        resolved = ResolvedFinanceUserInput.model_validate(
            run_input.response_data
        )
    except ValidationError as exc:
        raise FinanceRunInputGroundingError(
            "Persisted Finance user answer is "
            "invalid"
        ) from exc

    if resolved.input_name.value != run_input.input_name:
        raise FinanceRunInputGroundingError(
            "Persisted Finance answer does not "
            "match its input_name column"
        )

    return resolved


def _user_assumption(
    *,
    resolved: ResolvedFinanceUserInput,
    run_input_id: UUID,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=resolved.input_name,
        value=resolved.value,
        provenance=(
            FinancialAssumptionProvenance.USER
        ),
        currency=resolved.currency,
        unit_label=resolved.unit_label,
        period=resolved.period,
        rationale=(
            "User supplied or explicitly "
            "selected this value during the "
            "active AnalysisRun."
        ),
        profile_fields=[],
        analysis_run_input_ids=[
            run_input_id
        ],
        supporting_stages=[],
        evidence_source_ids=[],
    )


def _replace_assumption(
    *,
    assumptions: FinancialAssumptionSet,
    replacement: FinancialAssumption,
) -> FinancialAssumptionSet:
    field_name = _INPUT_FIELDS[
        replacement.input_name
    ]

    values = {
        "scenario": assumptions.scenario,
        "selling_price_per_unit": (
            assumptions.selling_price_per_unit
        ),
        "sales_volume": assumptions.sales_volume,
        "variable_cost_per_unit": (
            assumptions.variable_cost_per_unit
        ),
        "fixed_costs": assumptions.fixed_costs,
        "starting_cash": assumptions.starting_cash,
    }
    values[field_name] = replacement

    return FinancialAssumptionSet(**values)


def apply_answered_finance_inputs(
    *,
    inputs: FinancialScenarioInputs,
    run_inputs: Sequence[AnalysisRunInput],
    analysis_run_id: UUID,
    stage_run_id: UUID,
) -> FinancialScenarioInputs:
    base = inputs.base
    upside = inputs.upside
    downside = inputs.downside

    # The caller loads answers in chronological order.
    # If the same input was deliberately requested
    # again later, the latest answered value wins.
    for run_input in run_inputs:
        resolved = _resolve_persisted_input(
            run_input=run_input,
            analysis_run_id=analysis_run_id,
            stage_run_id=stage_run_id,
        )
        replacement = _user_assumption(
            resolved=resolved,
            run_input_id=run_input.id,
        )

        base = _replace_assumption(
            assumptions=base,
            replacement=replacement,
        )
        upside = _replace_assumption(
            assumptions=upside,
            replacement=replacement,
        )
        downside = _replace_assumption(
            assumptions=downside,
            replacement=replacement,
        )

    return FinancialScenarioInputs(
        base=base,
        upside=upside,
        downside=downside,
    )
