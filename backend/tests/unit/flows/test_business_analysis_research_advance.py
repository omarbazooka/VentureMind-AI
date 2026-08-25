from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
)
from app.schemas.analysis import AnalysisStage


def test_advance_research_schedules_gate_retries(
    monkeypatch,
):
    evaluation = SimpleNamespace(
        gate=SimpleNamespace(
            retry_stages=[
                AnalysisStage.CUSTOMER_INTELLIGENCE
            ]
        )
    )
    inspect = Mock(return_value=evaluation)
    retry = SimpleNamespace(
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE,
        stage_run_id=uuid4(),
        attempt=2,
    )
    schedule = Mock(return_value=[retry])

    monkeypatch.setattr(
        "app.flows.business_analysis_flow.inspect_research_join",
        inspect,
    )
    monkeypatch.setattr(
        "app.flows.business_analysis_flow.schedule_targeted_retries",
        schedule,
    )

    db = Mock()
    run_id = uuid4()

    result = BusinessAnalysisFlow().advance_research(
        db=db,
        run_id=run_id,
    )

    assert result.evaluation is evaluation
    assert result.scheduled_retries == [retry]
    inspect.assert_called_once()
    schedule.assert_called_once()


def test_advance_research_does_not_schedule_without_retry(
    monkeypatch,
):
    evaluation = SimpleNamespace(
        gate=SimpleNamespace(
            retry_stages=[]
        )
    )

    monkeypatch.setattr(
        "app.flows.business_analysis_flow.inspect_research_join",
        Mock(return_value=evaluation),
    )
    schedule = Mock()
    monkeypatch.setattr(
        "app.flows.business_analysis_flow.schedule_targeted_retries",
        schedule,
    )

    result = BusinessAnalysisFlow().advance_research(
        db=Mock(),
        run_id=uuid4(),
    )

    assert result.scheduled_retries == []
    schedule.assert_not_called()
