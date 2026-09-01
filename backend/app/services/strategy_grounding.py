from typing import Any

from pydantic import BaseModel

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategicClaimKind,
    StrategicInsight,
    StrategyStageClaim,
)


STRATEGY_INSIGHT_FIELDS = (
    "positioning",
    "value_proposition",
    "business_model_implications",
    "go_to_market",
    "strategic_strengths",
    "strategic_weaknesses",
    "critical_assumptions",
)


class StrategyGroundingError(
    RuntimeError
):
    pass


def _iter_strategy_insights(
    analysis: BusinessStrategyAnalysis,
) -> list[StrategicInsight]:
    insights: list[StrategicInsight] = []

    for field_name in STRATEGY_INSIGHT_FIELDS:
        insights.extend(
            getattr(
                analysis,
                field_name,
            )
        )

    return insights


def _collect_source_ids(
    value: Any,
) -> set[str]:
    source_ids: set[str] = set()

    if isinstance(value, dict):
        for key, child in value.items():
            if (
                key == "evidence_source_ids"
                and isinstance(child, list)
            ):
                source_ids.update(
                    source_id
                    for source_id in child
                    if isinstance(
                        source_id,
                        str,
                    )
                )

            elif (
                key == "primary_source_id"
                and isinstance(child, str)
            ):
                source_ids.add(child)

            source_ids.update(
                _collect_source_ids(
                    child
                )
            )

        return source_ids

    if isinstance(value, list):
        for child in value:
            source_ids.update(
                _collect_source_ids(
                    child
                )
            )

    return source_ids


def _visible_source_ids(
    analysis: BaseModel,
) -> set[str]:
    payload = analysis.model_dump(
        mode="json",
        exclude={
            "evidence_sources",
        },
    )

    return _collect_source_ids(
        payload
    )


def _research_results_by_stage(
    claim: StrategyStageClaim,
) -> dict[
    AnalysisStage,
    BaseModel | None,
]:
    return {
        AnalysisStage.MARKET_RESEARCH: (
            claim.market_analysis
        ),
        AnalysisStage.COMPETITOR_INTELLIGENCE: (
            claim.competitor_analysis
        ),
        AnalysisStage.CUSTOMER_INTELLIGENCE: (
            claim.customer_analysis
        ),
    }


def _validate_profile_fields(
    *,
    insight: StrategicInsight,
    claim: StrategyStageClaim,
) -> None:
    known_fields = set(
        claim
        .profile_snapshot
        .profile_data
        .keys()
    )

    unknown_fields = (
        set(insight.profile_fields)
        - known_fields
    )

    if unknown_fields:
        raise StrategyGroundingError(
            "Strategy insight referenced "
            "unknown IdeaProfile fields: "
            f"{sorted(unknown_fields)}"
        )


def _validate_profile_fact(
    insight: StrategicInsight,
) -> None:
    if insight.supporting_stages:
        raise StrategyGroundingError(
            "PROFILE_FACT cannot use "
            "research stages as its "
            "provenance"
        )

    if insight.evidence_source_ids:
        raise StrategyGroundingError(
            "PROFILE_FACT cannot cite "
            "research evidence sources"
        )


def _validate_ai_assumption(
    insight: StrategicInsight,
) -> None:
    if (
        insight.supporting_stages
        or insight.evidence_source_ids
        or insight.profile_fields
    ):
        raise StrategyGroundingError(
            "AI_ASSUMPTION must remain "
            "explicitly unverified and "
            "cannot claim profile or "
            "research provenance"
        )


def _validate_research_inference(
    *,
    insight: StrategicInsight,
    claim: StrategyStageClaim,
) -> None:
    results_by_stage = (
        _research_results_by_stage(
            claim
        )
    )

    visible_source_ids: set[str] = set()

    for stage in insight.supporting_stages:
        research_result = (
            results_by_stage.get(stage)
        )

        if research_result is None:
            raise StrategyGroundingError(
                "Strategy inference referenced "
                "a research stage without an "
                "available accepted result: "
                f"{stage.value}"
            )

        visible_source_ids.update(
            _visible_source_ids(
                research_result
            )
        )

    unknown_source_ids = (
        set(
            insight.evidence_source_ids
        )
        - visible_source_ids
    )

    if unknown_source_ids:
        raise StrategyGroundingError(
            "Strategy inference referenced "
            "evidence source IDs that were "
            "not present in its supporting "
            "research inputs: "
            f"{sorted(unknown_source_ids)}"
        )


def finalize_business_strategy(
    *,
    analysis: BusinessStrategyAnalysis,
    claim: StrategyStageClaim,
) -> BusinessStrategyAnalysis:
    if (
        claim.stage
        != AnalysisStage.BUSINESS_STRATEGY
    ):
        raise StrategyGroundingError(
            "Business Strategy finalization "
            "requires a BUSINESS_STRATEGY "
            "claim"
        )

    if (
        claim.research_gate
        .insufficient_stages
        and not analysis.limitations
    ):
        raise StrategyGroundingError(
            "Strategy must surface limitations "
            "when the Research Evidence Gate "
            "contains insufficient stages"
        )

    for insight in _iter_strategy_insights(
        analysis
    ):
        _validate_profile_fields(
            insight=insight,
            claim=claim,
        )

        if (
            insight.claim_kind
            == StrategicClaimKind
            .PROFILE_FACT
        ):
            _validate_profile_fact(
                insight
            )

        elif (
            insight.claim_kind
            == StrategicClaimKind
            .RESEARCH_INFERENCE
        ):
            _validate_research_inference(
                insight=insight,
                claim=claim,
            )

        elif (
            insight.claim_kind
            == StrategicClaimKind
            .AI_ASSUMPTION
        ):
            _validate_ai_assumption(
                insight
            )

        else:
            raise StrategyGroundingError(
                "Strategy contains an "
                "unsupported claim kind"
            )

    return (
        BusinessStrategyAnalysis
        .model_validate(
            analysis.model_dump(
                mode="json"
            )
        )
    )