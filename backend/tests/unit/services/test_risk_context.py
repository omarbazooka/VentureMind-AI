from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.risk_context import (
    RiskContextDependencyError,
    build_risk_analysis_context,
)


def _unknown_assumption(
    input_name: FinancialInputName,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        rationale="Unknown test fixture input.",
    )


def _dummy_assumptions(
    scenario: FinancialScenarioKind,
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=_unknown_assumption(
            FinancialInputName.SELLING_PRICE_PER_UNIT
        ),
        sales_volume=_unknown_assumption(
            FinancialInputName.SALES_VOLUME
        ),
        variable_cost_per_unit=_unknown_assumption(
            FinancialInputName.VARIABLE_COST_PER_UNIT
        ),
        fixed_costs=_unknown_assumption(
            FinancialInputName.FIXED_COSTS
        ),
    )


def _dummy_result(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioResult:
    return FinancialScenarioResult(
        scenario=scenario,
        assumptions=_dummy_assumptions(scenario),
    )


def _dummy_bundle() -> FinancialScenarioBundle:
    return FinancialScenarioBundle(
        base=_dummy_result(FinancialScenarioKind.BASE),
        upside=_dummy_result(FinancialScenarioKind.UPSIDE),
        downside=_dummy_result(FinancialScenarioKind.DOWNSIDE),
    )


def _insufficient_research_gate() -> ResearchEvidenceGateResult:
    stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    assessments = [
        ResearchStageGateAssessment(
            stage=stage,
            attempt=1,
            stage_status=AnalysisStageStatus.COMPLETED,
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        )
        for stage in stages
    ]
    return ResearchEvidenceGateResult(
        decision=ResearchGateDecision.INSUFFICIENT,
        can_proceed=True,
        assessments=assessments,
        insufficient_stages=stages,
    )


def test_builds_risk_context_from_authoritative_upstream_results():
    run_id = uuid4()
    finance_stage_id = uuid4()
    gate = _insufficient_research_gate()
    evaluation = SimpleNamespace(
        gate=gate,
        results={},
    )
    snapshot = AnalysisProfileSnapshot(
        readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
        profile_data={"idea_description": "Gym SaaS"},
    )
    analysis_run = SimpleNamespace(
        id=run_id,
        profile_snapshot=snapshot.model_dump(mode="json"),
    )
    strategy_result = SimpleNamespace(
        stage_run_id=uuid4(),
        result_data=BusinessStrategyAnalysis(
            executive_summary="Proceed with caution."
        ).model_dump(mode="json"),
    )
    finance_bundle = _dummy_bundle()
    finance_result = SimpleNamespace(
        stage_run_id=finance_stage_id,
        result_data=finance_bundle.model_dump(mode="json"),
    )
    analytics_result = SimpleNamespace(
        stage_run_id=uuid4(),
        result_data=DecisionAnalyticsResult(
            finance_stage_run_id=finance_stage_id
        ).model_dump(mode="json"),
    )
    db = Mock()
    db.get.return_value = analysis_run

    with patch(
        "app.services.risk_context.inspect_research_join",
        return_value=evaluation,
    ), patch(
        "app.services.risk_context._load_completed_stage_result",
        side_effect=[
            strategy_result,
            finance_result,
            analytics_result,
        ],
    ):
        context = build_risk_analysis_context(
            db=db,
            analysis_run_id=run_id,
        )

    assert context.finance_stage_run_id == finance_stage_id
    assert (
        context.decision_analytics.finance_stage_run_id
        == finance_stage_id
    )
    assert context.business_strategy.executive_summary == (
        "Proceed with caution."
    )


def test_risk_context_requires_existing_analysis_run():
    db = Mock()
    db.get.return_value = None

    with pytest.raises(RiskContextDependencyError):
        build_risk_analysis_context(
            db=db,
            analysis_run_id=uuid4(),
        )
