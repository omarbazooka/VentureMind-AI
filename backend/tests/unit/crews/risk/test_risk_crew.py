from unittest.mock import Mock
from uuid import uuid4

import pytest
from crewai import Process
from crewai.crews.crew_output import CrewOutput
from crewai.llms.base_llm import BaseLLM

from app.crews.risk.crew import (
    RiskCrewError,
    RiskCrewRunner,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import ResearchEvidenceGateResult
from app.schemas.risk import (
    RiskCategory,
    RiskDraft,
    RiskDraftAnalysis,
    RiskImpact,
    RiskLikelihood,
)
from app.schemas.risk_runtime import RiskAnalysisContext
from app.schemas.strategy import BusinessStrategyAnalysis


class FakeLLM(BaseLLM):
    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        return "{}"


def make_context() -> RiskAnalysisContext:
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
    bundle = FinancialScenarioBundle.model_construct(
        base=None,
        upside=None,
        downside=None,
        comparisons=[],
        limitations=[],
    )
    return RiskAnalysisContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={
                "idea_description": "Gym management SaaS",
                "target_country": "Egypt",
            },
        ),
        research_gate=gate,
        business_strategy_stage_run_id=uuid4(),
        business_strategy=BusinessStrategyAnalysis(
            executive_summary="Proceed cautiously."
        ),
        finance_stage_run_id=finance_stage_id,
        finance_bundle=bundle,
        analytics_stage_run_id=uuid4(),
        decision_analytics=DecisionAnalyticsResult(
            finance_stage_run_id=finance_stage_id
        ),
    )


def make_result() -> RiskDraftAnalysis:
    return RiskDraftAnalysis(
        executive_summary="Execution uncertainty remains material.",
        risks=[
            RiskDraft(
                category=RiskCategory.EXECUTION,
                title="Execution capacity",
                statement="The strategy depends on execution assumptions that remain unvalidated.",
                likelihood=RiskLikelihood.MEDIUM,
                impact=RiskImpact.MEDIUM,
                confidence=0.7,
                rationale="The supplied strategy contains unresolved critical assumptions.",
                supporting_stages=[AnalysisStage.BUSINESS_STRATEGY],
            )
        ],
    )


def make_runner() -> RiskCrewRunner:
    return RiskCrewRunner(
        llm=FakeLLM(
            model="fake-model",
            provider="fake",
        )
    )


def test_builds_risk_crew_without_tools():
    runner = make_runner()
    crew = runner.build_crew()

    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1
    assert crew.process == Process.sequential
    assert crew.agents[0].role == "Venture Risk Analyst"
    assert crew.agents[0].allow_delegation is False
    assert crew.tasks[0].tools == []
    assert crew.tasks[0].output_pydantic is RiskDraftAnalysis
    assert "Do not perform web research" in crew.tasks[0].description
    assert "Do not output risk_score" in crew.tasks[0].description
    assert "INSUFFICIENT_EVIDENCE" in crew.tasks[0].description


def test_runner_returns_structured_risk_draft(monkeypatch):
    runner = make_runner()
    fake_crew = Mock()
    fake_crew.kickoff.return_value = CrewOutput(
        raw="",
        pydantic=make_result(),
    )
    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    result = runner(make_context())

    assert isinstance(result, RiskDraftAnalysis)
    assert result.risks[0].category == RiskCategory.EXECUTION
    inputs = fake_crew.kickoff.call_args.kwargs["inputs"]
    assert "Gym management SaaS" in inputs["profile_snapshot"]
    assert "Proceed cautiously" in inputs["business_strategy"]
    assert "finance_stage_run_id" not in inputs["finance_bundle"]


def test_runner_is_single_use(monkeypatch):
    runner = make_runner()
    fake_crew = Mock()
    fake_crew.kickoff.return_value = CrewOutput(
        raw="",
        pydantic=make_result(),
    )
    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    context = make_context()
    runner(context)

    with pytest.raises(RiskCrewError):
        runner(context)


def test_runner_rejects_missing_structured_output(monkeypatch):
    runner = make_runner()
    fake_crew = Mock()
    fake_crew.kickoff.return_value = CrewOutput(
        raw="unstructured",
        pydantic=None,
    )
    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    with pytest.raises(RiskCrewError):
        runner(make_context())
