from unittest.mock import Mock
from uuid import uuid4

import pytest
from crewai import Process
from crewai.crews.crew_output import (
    CrewOutput,
)
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool

from app.crews.market_research.crew import (
    MarketResearchCrewError,
    MarketResearchCrewRunner,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    MarketAnalysis,
    ResearchEvidenceQuality,
    ResearchStageClaim,
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


class FakeMarketResearchTool(BaseTool):
    name: str = "fake_market_research"
    description: str = (
        "Returns deterministic fake market "
        "evidence for tests."
    )

    def _run(
        self,
        query: str,
    ) -> str:
        return (
            "Fake market evidence "
            f"for query: {query}"
        )


def make_claim(
    *,
    stage: AnalysisStage = (
        AnalysisStage.MARKET_RESEARCH
    ),
) -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=stage,
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
                    "target_country": "Egypt",
                },
                profile_metadata={},
                unknown_fields=[],
            )
        ),
    )


def make_market_result() -> MarketAnalysis:
    return MarketAnalysis(
        summary=(
            "External market evidence "
            "is not available in this unit test."
        ),
        findings=[],
        evidence_sources=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "This test does not perform "
            "real external research."
        ],
    )


def make_runner() -> MarketResearchCrewRunner:
    return MarketResearchCrewRunner(
        llm=FakeLLM(
            model="fake-model",
            provider="fake",
        ),
        research_tool=(
            FakeMarketResearchTool()
        ),
    )


def test_builds_market_crew():
    runner = make_runner()

    crew = runner.build_crew()

    assert len(crew.agents) == 1
    assert len(crew.tasks) == 1

    agent = crew.agents[0]
    task = crew.tasks[0]

    assert (
        "RESEARCH SUBJECT LOCK"
        in task.description
    )

    assert (
        "Do NOT research the market research "
        "industry"
        in task.description
    )

    assert (
        "target geography"
        in task.description
    )

    assert (
        "Never substitute a different industry"
        in task.description
    )

    assert (
        agent.role
        == "Market Research Analyst"
    )

    assert agent.allow_delegation is False

    assert agent.max_iter == 6

    assert crew.process == Process.sequential

    assert task.agent is agent

    assert task.output_pydantic is MarketAnalysis

    assert len(task.tools) == 1

    assert (
        task.tools[0].name
        == "fake_market_research"
    )


def test_runner_returns_market_analysis(
    monkeypatch,
):
    runner = make_runner()

    claim = make_claim()

    market_result = make_market_result()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="",
            pydantic=market_result,
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    result = runner(claim)

    assert isinstance(
        result,
        MarketAnalysis,
    )

    assert result == market_result

    fake_crew.kickoff.assert_called_once()

    kickoff_inputs = (
        fake_crew
        .kickoff
        .call_args
        .kwargs["inputs"]
    )

    assert "profile_snapshot" in kickoff_inputs

    assert "Gym management SaaS" in (
        kickoff_inputs["profile_snapshot"]
    )


def test_runner_rejects_non_market_stage():
    runner = make_runner()

    claim = make_claim(
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    with pytest.raises(
        MarketResearchCrewError
    ):
        runner(claim)


def test_runner_rejects_missing_structured_output(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="unstructured result",
            pydantic=None,
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    with pytest.raises(
        MarketResearchCrewError
    ):
        runner(
            make_claim()
        )