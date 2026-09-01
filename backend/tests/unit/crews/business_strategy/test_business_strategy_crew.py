from unittest.mock import Mock
from uuid import uuid4

import pytest
from crewai import Process
from crewai.crews.crew_output import (
    CrewOutput,
)
from crewai.llms.base_llm import BaseLLM

from app.crews.business_strategy.crew import (
    BusinessStrategyCrewError,
    BusinessStrategyCrewRunner,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategyStageClaim,
)


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


def make_claim() -> StrategyStageClaim:
    research_stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]

    gate = ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision
            .INSUFFICIENT
        ),
        can_proceed=True,
        assessments=[
            ResearchStageGateAssessment(
                stage=stage,
                attempt=1,
                stage_status=(
                    AnalysisStageStatus
                    .COMPLETED
                ),
                evidence_quality=(
                    ResearchEvidenceQuality
                    .INSUFFICIENT
                ),
            )
            for stage in research_stages
        ],
        insufficient_stages=(
            research_stages
        ),
    )

    return StrategyStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
        ),
        attempt=1,
        profile_snapshot=(
            AnalysisProfileSnapshot(
                readiness=(
                    ProfileReadinessStatus
                    .READY_FOR_ANALYSIS
                ),
                profile_data={
                    "idea_description": (
                        "Gym management SaaS"
                    ),
                    "target_customers": [
                        "Independent gym owners"
                    ],
                    "target_country": (
                        "Egypt"
                    ),
                },
            )
        ),
        research_gate=gate,
    )


def make_result() -> BusinessStrategyAnalysis:
    return BusinessStrategyAnalysis(
        executive_summary=(
            "Evidence is insufficient for "
            "strong strategic conclusions."
        ),
        limitations=[
            "Market, competitor, and customer "
            "evidence are insufficient."
        ],
        finance_questions=[
            "What is the expected "
            "selling price?"
        ],
    )


def make_runner() -> BusinessStrategyCrewRunner:
    return BusinessStrategyCrewRunner(
        llm=FakeLLM(
            model="fake-model",
            provider="fake",
        ),
    )


def test_builds_business_strategy_crew():
    runner = make_runner()

    crew = runner.build_crew()

    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1

    assert (
        crew.process
        == Process.sequential
    )

    agent = crew.agents[0]
    task = crew.tasks[0]

    assert (
        agent.role
        == "Business Strategy Analyst"
    )

    assert agent.allow_delegation is False
    assert agent.max_iter == 4

    assert task.agent is agent
    assert task.tools == []

    assert (
        task.output_pydantic
        is BusinessStrategyAnalysis
    )

    assert (
        "Do not perform web research"
        in task.description
    )

    assert (
        "FINANCE BOUNDARY"
        in task.description
    )

    assert (
        "INSUFFICIENT_EVIDENCE"
        in task.description
    )


def test_runner_returns_structured_strategy(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="",
            pydantic=make_result(),
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(
            return_value=fake_crew
        ),
    )

    result = runner(
        make_claim()
    )

    assert isinstance(
        result,
        BusinessStrategyAnalysis,
    )

    assert (
        result.finance_questions
        == [
            "What is the expected "
            "selling price?"
        ]
    )

    fake_crew.kickoff.assert_called_once()

    inputs = (
        fake_crew
        .kickoff
        .call_args
        .kwargs["inputs"]
    )

    assert (
        "Gym management SaaS"
        in inputs["profile_snapshot"]
    )

    assert (
        inputs["market_analysis"]
        == "null"
    )


def test_runner_is_single_use(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="",
            pydantic=make_result(),
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(
            return_value=fake_crew
        ),
    )

    claim = make_claim()

    runner(claim)

    with pytest.raises(
        BusinessStrategyCrewError
    ):
        runner(claim)


def test_runner_rejects_missing_structured_output(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="unstructured",
            pydantic=None,
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(
            return_value=fake_crew
        ),
    )

    with pytest.raises(
        BusinessStrategyCrewError
    ):
        runner(
            make_claim()
        )