from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
    BusinessAnalysisRunNotFoundError,
    BusinessAnalysisRunStateError,
    BusinessAnalysisSnapshotError,
)
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import (
    AnalysisStageRun,
)
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)


def make_ready_snapshot() -> dict:
    return {
        "readiness": "READY_FOR_ANALYSIS",
        "profile_data": {
            "idea_description": (
                "A SaaS platform for "
                "independent gyms."
            ),
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        "profile_metadata": {
            "idea_description": {
                "provenance": "USER",
            },
            "target_customers": {
                "provenance": "USER",
            },
            "target_country": {
                "provenance": "USER",
            },
        },
        "unknown_fields": [],
    }


def make_run(
    *,
    status: str = "QUEUED",
) -> AnalysisRun:
    return AnalysisRun(
        id=uuid4(),
        idea_id=uuid4(),
        profile_id=uuid4(),
        profile_version=3,
        profile_snapshot=(
            make_ready_snapshot()
        ),
        status=status,
    )


def make_db(
    *,
    analysis_run: (
        AnalysisRun | None
    ),
    existing_stage_runs: (
        list[AnalysisStageRun]
        | None
    ) = None,
) -> Mock:
    db = Mock(spec=Session)

    db.scalar.return_value = (
        analysis_run
    )

    db.scalars.return_value.all.return_value = (
        existing_stage_runs
        or []
    )

    return db


def test_initializes_run_and_three_stages():
    analysis_run = make_run()

    db = make_db(
        analysis_run=analysis_run
    )

    result = (
        BusinessAnalysisFlow()
        .initialize(
            db=db,
            run_id=analysis_run.id,
        )
    )

    assert result is analysis_run

    assert (
        analysis_run.status
        == AnalysisRunStatus.RUNNING.value
    )

    assert (
        analysis_run.started_at
        is not None
    )

    stage_runs = [
        call.args[0]
        for call
        in db.add.call_args_list
    ]

    assert len(stage_runs) == 3

    assert {
        stage_run.stage
        for stage_run in stage_runs
    } == {
        AnalysisStage
        .MARKET_RESEARCH.value,
        AnalysisStage
        .COMPETITOR_INTELLIGENCE.value,
        AnalysisStage
        .CUSTOMER_INTELLIGENCE.value,
    }

    assert all(
        stage_run.status
        == AnalysisStageStatus.PENDING.value
        for stage_run in stage_runs
    )

    db.flush.assert_called_once_with()


def test_running_run_initialization_is_idempotent():
    started_at = datetime.now(
        timezone.utc
    )

    analysis_run = make_run(
        status=(
            AnalysisRunStatus.RUNNING.value
        )
    )

    analysis_run.started_at = started_at

    existing_market = AnalysisStageRun(
        analysis_run_id=analysis_run.id,
        stage=(
            AnalysisStage
            .MARKET_RESEARCH.value
        ),
        attempt=1,
        status=(
            AnalysisStageStatus
            .PENDING.value
        ),
    )

    db = make_db(
        analysis_run=analysis_run,
        existing_stage_runs=[
            existing_market
        ],
    )

    BusinessAnalysisFlow().initialize(
        db=db,
        run_id=analysis_run.id,
    )

    stage_runs = [
        call.args[0]
        for call
        in db.add.call_args_list
    ]

    assert len(stage_runs) == 2

    assert (
        AnalysisStage
        .MARKET_RESEARCH.value
        not in {
            stage_run.stage
            for stage_run in stage_runs
        }
    )

    assert (
        analysis_run.started_at
        == started_at
    )


def test_missing_run_is_rejected():
    db = make_db(
        analysis_run=None
    )

    with pytest.raises(
        BusinessAnalysisRunNotFoundError
    ):
        BusinessAnalysisFlow().initialize(
            db=db,
            run_id=uuid4(),
        )

    db.add.assert_not_called()


def test_terminal_run_is_rejected():
    analysis_run = make_run(
        status=(
            AnalysisRunStatus
            .COMPLETED.value
        )
    )

    db = make_db(
        analysis_run=analysis_run
    )

    with pytest.raises(
        BusinessAnalysisRunStateError
    ):
        BusinessAnalysisFlow().initialize(
            db=db,
            run_id=analysis_run.id,
        )

    db.add.assert_not_called()


def test_invalid_snapshot_is_rejected():
    analysis_run = make_run()

    analysis_run.profile_snapshot = {
        "readiness": (
            "READY_FOR_ANALYSIS"
        ),
        "profile_data": {},
        "profile_metadata": {},
        "unknown_fields": [],
    }

    db = make_db(
        analysis_run=analysis_run
    )

    with pytest.raises(
        BusinessAnalysisSnapshotError
    ):
        BusinessAnalysisFlow().initialize(
            db=db,
            run_id=analysis_run.id,
        )

    assert (
        analysis_run.status
        == AnalysisRunStatus.QUEUED.value
    )

    db.add.assert_not_called()