from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import (
    FinancialAssumptionSet,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import ResearchEvidenceGateResult
from app.schemas.risk_runtime import RiskAnalysisContext
from app.schemas.strategy import BusinessStrategyAnalysis


def _dummy_result(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioResult:
    assumptions = FinancialAssumptionSet.model_construct(
        scenario=scenario,
    )
    return FinancialScenarioResult.model_construct(
        scenario=scenario,
        assumptions=assumptions,
        metrics=[],
        missing_critical_inputs=[],
        limitations=[],
    )


def _dummy_bundle() -> FinancialScenarioBundle:
    return FinancialScenarioBundle.model_construct(
        base=_dummy_result(FinancialScenarioKind.BASE),
        upside=_dummy_result(FinancialScenarioKind.UPSIDE),
        downside=_dummy_result(FinancialScenarioKind.DOWNSIDE),
        comparisons=[],
        limitations=[],
    )


def make_context(*, analytics_finance_id=None, finance_id=None):
    finance_stage_run_id = finance_id or uuid4()
    analytics_finance_id = (
        analytics_finance_id or finance_stage_run_id
    )
    research_stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    gate = ResearchEvidenceGateResult.model_construct(
        can_proceed=True,
        insufficient_stages=research_stages,
    )
    bundle = _dummy_bundle()

    return {
        "profile_snapshot": AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={"idea_description": "Gym SaaS"},
        ),
        "research_gate": gate,
        "business_strategy_stage_run_id": uuid4(),
        "business_strategy": BusinessStrategyAnalysis(
            executive_summary="Proceed with caution."
        ),
        "finance_stage_run_id": finance_stage_run_id,
        "finance_bundle": bundle,
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
