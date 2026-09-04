from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
)
from app.schemas.analysis import (
    AnalysisStage,
)


def test_advance_research_schedules_gate_retries(
    monkeypatch,
):
    evaluation = SimpleNamespace(
        gate=SimpleNamespace(
            retry_stages=[
                AnalysisStage
                .CUSTOMER_INTELLIGENCE
            ],
            can_proceed=False,
        )
    )

    inspect = Mock(
        return_value=evaluation
    )

    retry = SimpleNamespace(
        stage=(
            AnalysisStage
            .CUSTOMER_INTELLIGENCE
        ),
        stage_run_id=uuid4(),
        attempt=2,
    )

    schedule = Mock(
        return_value=[retry]
    )

    flow = BusinessAnalysisFlow()

    strategy_schedule = Mock()

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "inspect_research_join"
        ),
        inspect,
    )

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "schedule_targeted_retries"
        ),
        schedule,
    )

    monkeypatch.setattr(
        flow,
        "_ensure_business_strategy_stage_run",
        strategy_schedule,
    )

    db = Mock()
    run_id = uuid4()

    result = flow.advance_research(
        db=db,
        run_id=run_id,
    )

    assert (
        result.evaluation
        is evaluation
    )

    assert (
        result.scheduled_retries
        == [retry]
    )

    assert (
        result.strategy_stage_run_id
        is None
    )

    inspect.assert_called_once()

    schedule.assert_called_once()

    strategy_schedule.assert_not_called()


def test_advance_research_schedules_strategy_when_gate_allows(
    monkeypatch,
):
    evaluation = SimpleNamespace(
        gate=SimpleNamespace(
            retry_stages=[],
            can_proceed=True,
        )
    )

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "inspect_research_join"
        ),
        Mock(
            return_value=evaluation
        ),
    )

    retry_schedule = Mock()

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "schedule_targeted_retries"
        ),
        retry_schedule,
    )

    strategy_stage_run_id = uuid4()

    strategy_stage_run = SimpleNamespace(
        id=strategy_stage_run_id
    )

    flow = BusinessAnalysisFlow()

    strategy_schedule = Mock(
        return_value=strategy_stage_run
    )

    monkeypatch.setattr(
        flow,
        "_ensure_business_strategy_stage_run",
        strategy_schedule,
    )

    db = Mock()
    run_id = uuid4()

    result = flow.advance_research(
        db=db,
        run_id=run_id,
    )

    assert (
        result.scheduled_retries
        == []
    )

    assert (
        result.strategy_stage_run_id
        == strategy_stage_run_id
    )

    retry_schedule.assert_not_called()

    strategy_schedule.assert_called_once_with(
        db=db,
        analysis_run_id=run_id,
    )


def test_advance_research_does_not_proceed_when_gate_blocks(
    monkeypatch,
):
    evaluation = SimpleNamespace(
        gate=SimpleNamespace(
            retry_stages=[],
            can_proceed=False,
        )
    )

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "inspect_research_join"
        ),
        Mock(
            return_value=evaluation
        ),
    )

    retry_schedule = Mock()

    monkeypatch.setattr(
        (
            "app.flows.business_analysis_flow."
            "schedule_targeted_retries"
        ),
        retry_schedule,
    )

    flow = BusinessAnalysisFlow()

    strategy_schedule = Mock()

    monkeypatch.setattr(
        flow,
        "_ensure_business_strategy_stage_run",
        strategy_schedule,
    )

    result = flow.advance_research(
        db=Mock(),
        run_id=uuid4(),
    )

    assert (
        result.scheduled_retries
        == []
    )

    assert (
        result.strategy_stage_run_id
        is None
    )

    retry_schedule.assert_not_called()

    strategy_schedule.assert_not_called()

def test_strategy_scheduling_reuses_existing_stage():
    run_id = uuid4()

    existing_stage = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        ),
        attempt=1,
        status="PENDING",
    )

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        existing_stage,
    ]

    result = (
        BusinessAnalysisFlow()
        ._ensure_business_strategy_stage_run(
            db=db,
            analysis_run_id=run_id,
        )
    )

    assert result is existing_stage

    db.add.assert_not_called()


def test_strategy_scheduling_creates_pending_stage():
    run_id = uuid4()

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        None,
    ]

    result = (
        BusinessAnalysisFlow()
        ._ensure_business_strategy_stage_run(
            db=db,
            analysis_run_id=run_id,
        )
    )

    assert (
        result.analysis_run_id
        == run_id
    )

    assert (
        result.stage
        == (
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        )
    )

    assert result.attempt == 1

    assert result.status == "PENDING"

    db.add.assert_called_once_with(
        result
    )

    db.flush.assert_called_once_with()