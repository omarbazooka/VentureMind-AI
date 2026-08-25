from unittest.mock import Mock
from uuid import uuid4

import pytest
from crewai import Process
from crewai.crews.crew_output import (
    CrewOutput,
)
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool

from app.crews.competitor_intelligence.crew import (
    CompetitorIntelligenceCrewError,
    CompetitorIntelligenceCrewRunner,
)
from app.research.competitor_evidence import (
    CompetitorAnalysisDraft,
)
from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
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


class FakeCompetitorResearchTool(
    BaseTool
):
    name: str = (
        "fake_competitor_research"
    )

    description: str = (
        "Returns deterministic fake "
        "competitor evidence for tests."
    )

    def _run(
        self,
        query: str,
    ) -> str:
        return (
            "Fake competitor evidence "
            f"for query: {query}"
        )


def make_claim(
    *,
    stage: AnalysisStage = (
        AnalysisStage
        .COMPETITOR_INTELLIGENCE
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


def make_draft(
) -> CompetitorAnalysisDraft:
    return CompetitorAnalysisDraft(
        summary=(
            "Reliable competitor evidence "
            "was not available in this "
            "unit test."
        ),
        findings=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "This unit test does not "
            "perform external research."
        ],
    )


def make_runner(
) -> CompetitorIntelligenceCrewRunner:
    return (
        CompetitorIntelligenceCrewRunner(
            llm=FakeLLM(
                model="fake-model",
                provider="fake",
            ),
            research_tool=(
                FakeCompetitorResearchTool()
            ),
            evidence_ledger=(
                ResearchEvidenceLedger(
                    stage=(
                        AnalysisStage
                        .COMPETITOR_INTELLIGENCE
                    )
                )
            ),
        )
    )


def test_builds_competitor_crew():
    runner = make_runner()

    crew = runner.build_crew()

    assert len(crew.agents) == 1
    assert len(crew.tasks) == 2

    agent = crew.agents[0]
    research_task = crew.tasks[0]
    synthesis_task = crew.tasks[1]

    assert (
        agent.role
        == (
            "Competitor Intelligence "
            "Analyst"
        )
    )

    assert (
        agent.allow_delegation
        is False
    )

    assert agent.max_iter == 6

    assert (
        crew.process
        == Process.sequential
    )

    assert research_task.agent is agent
    assert synthesis_task.agent is agent

    assert (
        "COMPETITIVE SUBJECT LOCK"
        in research_task.description
    )

    assert (
        "direct competitors"
        in research_task.description
    )

    assert (
        "indirect alternatives"
        in research_task.description
    )

    assert (
        "Pricing must not be guessed"
        in research_task.description
    )

    assert (
        research_task.output_pydantic
        is None
    )

    assert (
        len(research_task.tools)
        == 1
    )

    assert (
        research_task.tools[0].name
        == "fake_competitor_research"
    )

    assert (
        synthesis_task.output_pydantic
        is CompetitorAnalysisDraft
    )

    assert (
        synthesis_task.tools
        == []
    )

    assert (
        synthesis_task.context
        is not None
    )

    assert (
        len(synthesis_task.context)
        == 1
    )

    assert (
        synthesis_task.context[0]
        is research_task
    )

    assert (
        "Do NOT output source URLs"
        in synthesis_task.description
    )

    assert (
        "WHITESPACE findings"
        in synthesis_task.description
    )


def test_runner_returns_competitor_analysis(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="",
            pydantic=make_draft(),
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

    assert (
        result.evidence_quality
        == (
            ResearchEvidenceQuality
            .INSUFFICIENT
        )
    )

    assert result.findings == []
    assert result.evidence_sources == []

    fake_crew.kickoff.assert_called_once()

    kickoff_inputs = (
        fake_crew
        .kickoff
        .call_args
        .kwargs["inputs"]
    )

    assert (
        "profile_snapshot"
        in kickoff_inputs
    )

    assert (
        "Gym management SaaS"
        in (
            kickoff_inputs[
                "profile_snapshot"
            ]
        )
    )


def test_runner_rejects_wrong_stage():
    runner = make_runner()

    claim = make_claim(
        stage=(
            AnalysisStage.MARKET_RESEARCH
        )
    )

    with pytest.raises(
        CompetitorIntelligenceCrewError
    ):
        runner(claim)


def test_runner_rejects_second_execution(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw="",
            pydantic=make_draft(),
        )
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(
            return_value=fake_crew
        ),
    )

    runner(
        make_claim()
    )

    with pytest.raises(
        CompetitorIntelligenceCrewError
    ):
        runner(
            make_claim()
        )


def test_runner_rejects_missing_structured_output(
    monkeypatch,
):
    runner = make_runner()

    fake_crew = Mock()

    fake_crew.kickoff.return_value = (
        CrewOutput(
            raw=(
                "Unstructured competitor "
                "analysis"
            ),
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
        CompetitorIntelligenceCrewError
    ):
        runner(
            make_claim()
        )


def test_runner_rejects_wrong_ledger_stage():
    with pytest.raises(
        ValueError
    ):
        CompetitorIntelligenceCrewRunner(
            llm=FakeLLM(
                model="fake-model",
                provider="fake",
            ),
            research_tool=(
                FakeCompetitorResearchTool()
            ),
            evidence_ledger=(
                ResearchEvidenceLedger(
                    stage=(
                        AnalysisStage
                        .MARKET_RESEARCH
                    )
                )
            ),
        )