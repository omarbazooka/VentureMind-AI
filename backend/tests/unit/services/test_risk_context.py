from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import ResearchEvidenceGateResult
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.risk_context import (
    RiskContextDependencyError,
    build_risk_analysis_context,
)


def test_builds_risk_context_from_authoritative_upstream_results():
    run_id = uuid4()
    finance_stage_id = uuid4()
    research_stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    gate = ResearchEvidenceGateResult.model_construct(
        can_proceed=True,
        insufficient_stages=research_stages,
    )
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
    finance_bundle = FinancialScenarioBundle.model_construct(
        base=None,
        upside=None,
        downside=None,
        comparisons=[],
        limitations=[],
    )
    finance_result = SimpleNamespace(
        stage_run_id=finance_stage_id,
        result_data=finance_bundle,
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
