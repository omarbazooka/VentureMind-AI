from unittest.mock import Mock
from uuid import uuid4

import pytest
from crewai import Process
from crewai.crews.crew_output import CrewOutput
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool

from app.crews.customer_intelligence.crew import (
    CustomerIntelligenceCrewError,
    CustomerIntelligenceCrewRunner,
)
from app.research.customer_evidence import (
    CustomerAnalysisDraft,
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
from app.schemas.tools import (
    WebSearchResult,
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


class FakeSearchTool(BaseTool):
    name: str = "controlled_web_search"
    description: str = "Fake controlled web search."

    def _run(
        self,
        query: str,
        max_results: int = 5,
    ) -> str:
        return "{}"


class FakePageTool(BaseTool):
    name: str = "controlled_batch_page_retrieval"
    description: str = "Fake page retrieval."

    def _run(
        self,
        urls: list[str],
        max_chars: int = 6_000,
    ) -> str:
        return "{}"


def make_claim(
    *,
    stage: AnalysisStage = AnalysisStage.CUSTOMER_INTELLIGENCE,
) -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=stage,
        attempt=1,
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={
                "idea_description": "Gym management SaaS",
                "target_customers": [
                    "Independent gym owners"
                ],
                "target_country": "Egypt",
            },
            profile_metadata={},
            unknown_fields=[],
        ),
    )


def make_draft() -> CustomerAnalysisDraft:
    return CustomerAnalysisDraft(
        summary="No reliable customer evidence in unit test.",
        findings=[],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=[
            "This unit test does not perform live research."
        ],
    )


def make_runner() -> CustomerIntelligenceCrewRunner:
    ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE
    )

    ledger.record_web_search_result(
        WebSearchResult(
            query="unit test customer search attempt",
            items=[],
        )
    )

    return CustomerIntelligenceCrewRunner(
        llm=FakeLLM(
            model="fake-model",
            provider="fake",
        ),
        search_tool=FakeSearchTool(),
        page_retrieval_tool=FakePageTool(),
        evidence_ledger=ledger,
    )


def test_builds_customer_crew():
    runner = make_runner()
    crew = runner.build_crew()

    assert len(crew.agents) == 1
    assert len(crew.tasks) == 2
    assert crew.process == Process.sequential

    agent = crew.agents[0]
    research_task = crew.tasks[0]
    synthesis_task = crew.tasks[1]

    assert agent.role == "Customer Intelligence Analyst"
    assert agent.allow_delegation is False
    assert agent.max_iter == 6

    assert research_task.agent is agent
    assert synthesis_task.agent is agent

    assert len(research_task.tools) == 2
    assert research_task.tools[0].name == "controlled_web_search"
    assert (
        research_task.tools[1].name
        == "controlled_batch_page_retrieval"
    )

    assert "Hard maximum of 3 search queries" in (
        research_task.description
    )
    assert "NOT A PERSONA GENERATOR" in (
        research_task.description
    )
    assert "DESK RESEARCH DOES NOT PROVE PMF" in (
        research_task.description
    )

    assert synthesis_task.tools == []
    assert synthesis_task.output_pydantic is CustomerAnalysisDraft
    assert synthesis_task.context == [research_task]
    assert "CustomerFinding categories" in (
        synthesis_task.description
    )


def test_runner_returns_customer_analysis(
    monkeypatch,
):
    runner = make_runner()
    fake_crew = Mock()
    fake_crew.kickoff.return_value = CrewOutput(
        raw="",
        pydantic=make_draft(),
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    result = runner(make_claim())

    assert (
        result.evidence_quality
        == ResearchEvidenceQuality.INSUFFICIENT
    )
    assert result.findings == []
    assert result.evidence_sources == []

    fake_crew.kickoff.assert_called_once()
    inputs = fake_crew.kickoff.call_args.kwargs["inputs"]
    assert "Gym management SaaS" in inputs["profile_snapshot"]


def test_runner_rejects_wrong_stage():
    runner = make_runner()

    with pytest.raises(
        CustomerIntelligenceCrewError
    ):
        runner(
            make_claim(
                stage=AnalysisStage.MARKET_RESEARCH
            )
        )


def test_runner_rejects_second_execution(
    monkeypatch,
):
    runner = make_runner()
    fake_crew = Mock()
    fake_crew.kickoff.return_value = CrewOutput(
        raw="",
        pydantic=make_draft(),
    )

    monkeypatch.setattr(
        runner,
        "build_crew",
        Mock(return_value=fake_crew),
    )

    runner(make_claim())

    with pytest.raises(
        CustomerIntelligenceCrewError
    ):
        runner(make_claim())


def test_runner_rejects_missing_structured_output(
    monkeypatch,
):
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

    with pytest.raises(
        CustomerIntelligenceCrewError
    ):
        runner(make_claim())


def test_runner_rejects_wrong_ledger_stage():
    with pytest.raises(ValueError):
        CustomerIntelligenceCrewRunner(
            llm=FakeLLM(
                model="fake-model",
                provider="fake",
            ),
            search_tool=FakeSearchTool(),
            page_retrieval_tool=FakePageTool(),
            evidence_ledger=ResearchEvidenceLedger(
                stage=AnalysisStage.MARKET_RESEARCH
            ),
        )
