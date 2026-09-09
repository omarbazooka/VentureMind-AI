from uuid import uuid4

import pytest
from pydantic import ValidationError

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
from app.schemas.risk_runtime import RiskAnalysisContext
from app.schemas.strategy import BusinessStrategyAnalysis


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


def make_context(*, analytics_finance_id=None, finance_id=None):
    finance_stage_run_id = finance_id or uuid4()
    analytics_finance_id = (
        analytics_finance_id or finance_stage_run_id
    )

    return {
        "profile_snapshot": AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={"idea_description": "Gym SaaS"},
        ),
        "research_gate": _insufficient_research_gate(),
        "business_strategy_stage_run_id": uuid4(),
        "business_strategy": BusinessStrategyAnalysis(
            executive_summary="Proceed with caution."
        ),
        "finance_stage_run_id": finance_stage_run_id,
        "finance_bundle": _dummy_bundle(),
        "analytics_stage_run_id": uuid4(),
        "decision_analytics": DecisionAnalyticsResult(
            finance_stage_run_id=analytics_finance_id
        ),
    }


def test_risk_context_accepts_consistent_finance_analytics_lineage():
    context = RiskAnalysisContext(**make_context())
    assert (
        context.decision_analytics.finance_stage_run_id
        == context.finance_stage_run_id
    )


def test_risk_context_rejects_mismatched_finance_analytics_lineage():
    with pytest.raises(ValidationError):
        RiskAnalysisContext(
            **make_context(
                finance_id=uuid4(),
                analytics_finance_id=uuid4(),
            )
        )
