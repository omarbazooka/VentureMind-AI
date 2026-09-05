import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.analysis import AnalysisStage
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialScenarioInputs,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
    FinancialAssumptionDraft,
    FinancialAssumptionDraftBundle,
    FinancialScenarioAssumptionDraft,
)
from app.schemas.research import EvidenceProvenance


class FinanceGroundingError(RuntimeError):
    pass


_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?"
)


def _decimal_values(value: Any) -> set[Decimal]:
    values: set[Decimal] = set()

    if value is None or isinstance(value, bool):
        return values

    if isinstance(value, Decimal):
        values.add(value)
        return values

    if isinstance(value, (int, float)):
        try:
            values.add(Decimal(str(value)))
        except InvalidOperation:
            pass
        return values

    if isinstance(value, str):
        for match in _NUMERIC_TOKEN_PATTERN.findall(value):
            normalized = match.replace(",", "")
            try:
                values.add(Decimal(normalized))
            except InvalidOperation:
                continue
        return values

    if isinstance(value, dict):
        for nested in value.values():
            values.update(_decimal_values(nested))
        return values

    if isinstance(value, (list, tuple, set)):
        for nested in value:
            values.update(_decimal_values(nested))

    return values


def _validate_user_grounding(
    *,
    draft: FinancialAssumptionDraft,
    context: FinanceAssumptionBuilderContext,
) -> None:
    if draft.value is None:
        raise FinanceGroundingError(
            "USER grounding requires a known value"
        )

    profile_data = context.profile_snapshot.profile_data

    unknown_fields = [
        field_name
        for field_name in draft.profile_fields
        if field_name not in profile_data
    ]

    if unknown_fields:
        raise FinanceGroundingError(
            "Finance draft references unknown "
            "IdeaProfile fields: "
            f"{sorted(unknown_fields)}"
        )

    value_is_supported = any(
        draft.value
        in _decimal_values(profile_data[field_name])
        for field_name in draft.profile_fields
    )

    if not value_is_supported:
        raise FinanceGroundingError(
            f"{draft.input_name.value} claims USER "
            "provenance but the claimed numeric value "
            "does not appear in its referenced "
            "IdeaProfile fields"
        )


def _research_by_stage(
    context: FinanceAssumptionBuilderContext,
) -> dict[AnalysisStage, Any | None]:
    return {
        AnalysisStage.MARKET_RESEARCH: context.market_analysis,
        AnalysisStage.COMPETITOR_INTELLIGENCE: (
            context.competitor_analysis
        ),
        AnalysisStage.CUSTOMER_INTELLIGENCE: (
            context.customer_analysis
        ),
    }


def _stage_web_source_ids(analysis: Any) -> set[str]:
    if analysis is None:
        return set()

    evidence_sources = getattr(
        analysis,
        "evidence_sources",
        [],
    )

    return {
        source.source_id
        for source in evidence_sources
        if source.provenance == EvidenceProvenance.WEB
    }


def _numeric_support_values(
    *,
    value: Any,
    source_ids: set[str],
) -> set[Decimal]:
    supported: set[Decimal] = set()

    if isinstance(value, dict):
        node_source_ids = set(
            value.get("evidence_source_ids", [])
        )

        if (
            value.get("is_numerical") is True
            and node_source_ids & source_ids
        ):
            supported.update(
                _decimal_values(value.get("statement"))
            )

        for nested in value.values():
            supported.update(
                _numeric_support_values(
                    value=nested,
                    source_ids=source_ids,
                )
            )

        return supported

    if isinstance(value, list):
        for nested in value:
            supported.update(
                _numeric_support_values(
                    value=nested,
                    source_ids=source_ids,
                )
            )

    return supported


def _validate_web_grounding(
    *,
    draft: FinancialAssumptionDraft,
    context: FinanceAssumptionBuilderContext,
) -> None:
    if draft.value is None:
        raise FinanceGroundingError(
            "WEB grounding requires a known value"
        )

    research_by_stage = _research_by_stage(context)
    insufficient_stages = set(
        context.research_gate.insufficient_stages
    )
    claimed_source_ids = set(
        draft.evidence_source_ids
    )
    allowed_source_ids: set[str] = set()

    for stage in draft.supporting_stages:
        if stage in insufficient_stages:
            raise FinanceGroundingError(
                f"{stage.value} is marked INSUFFICIENT "
                "and cannot provide authoritative WEB "
                "financial grounding"
            )

        analysis = research_by_stage.get(stage)
        if analysis is None:
            raise FinanceGroundingError(
                "WEB financial grounding references "
                "unavailable research stage "
                f"{stage.value}"
            )

        stage_source_ids = _stage_web_source_ids(
            analysis
        )
        cited_for_stage = (
            claimed_source_ids & stage_source_ids
        )

        if not cited_for_stage:
            raise FinanceGroundingError(
                f"{stage.value} is claimed as supporting "
                "research but none of its WEB evidence "
                "source IDs were cited"
            )

        allowed_source_ids.update(
            stage_source_ids
        )

    unknown_source_ids = (
        claimed_source_ids - allowed_source_ids
    )

    if unknown_source_ids:
        raise FinanceGroundingError(
            "Finance draft references unknown or "
            "non-WEB evidence source IDs: "
            f"{sorted(unknown_source_ids)}"
        )

    supported_values: set[Decimal] = set()

    for stage in draft.supporting_stages:
        analysis = research_by_stage[stage]
        stage_claimed_source_ids = (
            claimed_source_ids
            & _stage_web_source_ids(analysis)
        )
        payload = analysis.model_dump(
            mode="python"
        )

        supported_values.update(
            _numeric_support_values(
                value=payload,
                source_ids=stage_claimed_source_ids,
            )
        )

    if draft.value not in supported_values:
        raise FinanceGroundingError(
            f"{draft.input_name.value} claims WEB "
            "provenance but its numeric value is not "
            "supported by the cited numerical research "
            "findings"
        )


def _ground_assumption(
    *,
    draft: FinancialAssumptionDraft,
    context: FinanceAssumptionBuilderContext,
) -> FinancialAssumption:
    if (
        draft.input_name
        == FinancialInputName.STARTING_CASH
        and draft.value is not None
        and draft.provenance
        != FinancialAssumptionProvenance.USER
    ):
        raise FinanceGroundingError(
            "Known starting cash must come from USER "
            "provenance. Finance must not guess "
            "available cash."
        )

    if (
        draft.provenance
        == FinancialAssumptionProvenance.USER
    ):
        _validate_user_grounding(
            draft=draft,
            context=context,
        )
    elif (
        draft.provenance
        == FinancialAssumptionProvenance.WEB
    ):
        _validate_web_grounding(
            draft=draft,
            context=context,
        )

    return FinancialAssumption(
        input_name=draft.input_name,
        value=draft.value,
        provenance=draft.provenance,
        currency=draft.currency,
        unit_label=draft.unit_label,
        period=draft.period,
        rationale=draft.rationale,
        profile_fields=[*draft.profile_fields],
        supporting_stages=[*draft.supporting_stages],
        evidence_source_ids=[
            *draft.evidence_source_ids
        ],
    )


def _ground_scenario(
    *,
    draft: FinancialScenarioAssumptionDraft,
    context: FinanceAssumptionBuilderContext,
) -> FinancialAssumptionSet:
    starting_cash = None

    if draft.starting_cash is not None:
        starting_cash = _ground_assumption(
            draft=draft.starting_cash,
            context=context,
        )

    return FinancialAssumptionSet(
        scenario=draft.scenario,
        selling_price_per_unit=(
            _ground_assumption(
                draft=draft.selling_price_per_unit,
                context=context,
            )
        ),
        sales_volume=_ground_assumption(
            draft=draft.sales_volume,
            context=context,
        ),
        variable_cost_per_unit=(
            _ground_assumption(
                draft=draft.variable_cost_per_unit,
                context=context,
            )
        ),
        fixed_costs=_ground_assumption(
            draft=draft.fixed_costs,
            context=context,
        ),
        starting_cash=starting_cash,
    )


def _validate_starting_cash_across_scenarios(
    inputs: FinancialScenarioInputs,
) -> None:
    cash_inputs = (
        inputs.base.starting_cash,
        inputs.upside.starting_cash,
        inputs.downside.starting_cash,
    )

    known_cash = [
        assumption
        for assumption in cash_inputs
        if (
            assumption is not None
            and assumption.value is not None
        )
    ]

    if not known_cash:
        return

    if len(known_cash) != 3:
        raise FinanceGroundingError(
            "Known starting cash must be preserved "
            "across BASE, UPSIDE, and DOWNSIDE "
            "scenarios"
        )

    fingerprints = {
        (
            assumption.value,
            assumption.currency,
            tuple(sorted(assumption.profile_fields)),
        )
        for assumption in known_cash
    }

    if len(fingerprints) != 1:
        raise FinanceGroundingError(
            "Starting cash cannot change between "
            "financial scenarios"
        )


def finalize_financial_assumptions(
    *,
    drafts: FinancialAssumptionDraftBundle,
    context: FinanceAssumptionBuilderContext,
) -> FinancialScenarioInputs:
    inputs = FinancialScenarioInputs(
        base=_ground_scenario(
            draft=drafts.base,
            context=context,
        ),
        upside=_ground_scenario(
            draft=drafts.upside,
            context=context,
        ),
        downside=_ground_scenario(
            draft=drafts.downside,
            context=context,
        ),
    )

    _validate_starting_cash_across_scenarios(
        inputs
    )

    return inputs
