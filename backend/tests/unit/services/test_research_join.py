from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    ResearchEvidenceQuality,
    ResearchGateDecision,
)
from app.services.research_join import (
    ResearchJoinNotReadyError,
    inspect_research_join,
    schedule_targeted_retries,
)


def _query_result(items):
    result = Mock()
    result.all.return_value = items
    return result


def _stage_run(
    *,
    run_id,
    stage,
    attempt=1,
    status=AnalysisStageStatus.COMPLETED,
):
    return AnalysisStageRun(
        id=uuid4(),
        analysis_run_id=run_id,
        stage=stage.value,
        attempt=attempt,
        status=status.value,
    )


def _analysis_result(stage_run):
    return AnalysisResult(
        id=uuid4(),
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=stage_run.stage,
        result_data={"placeholder": True},
    )


def _db_for_join(*, run, stage_runs, results):
    db = Mock(spec=Session)
    db.get.return_value = run
    db.scalars.side_effect = [
        _query_result(stage_runs),
        _query_result(results),
    ]
    return db


def test_join_accepts_three_completed_results(monkeypatch):
    run = AnalysisRun(
        id=uuid4(),
        status=AnalysisRunStatus.RUNNING.value,
    )
    stages = [
        _stage_run(run_id=run.id, stage=AnalysisStage.MARKET_RESEARCH),
        _stage_run(run_id=run.id, stage=AnalysisStage.COMPETITOR_INTELLIGENCE),
        _stage_run(run_id=run.id, stage=AnalysisStage.CUSTOMER_INTELLIGENCE),
    ]
    results = [_analysis_result(stage_run) for stage_run in stages]
    quality_by_stage = {
        AnalysisStage.MARKET_RESEARCH: ResearchEvidenceQuality.STRONG,
        AnalysisStage.COMPETITOR_INTELLIGENCE: ResearchEvidenceQuality.MODERATE,
        AnalysisStage.CUSTOMER_INTELLIGENCE: ResearchEvidenceQuality.MODERATE,
    }

    monkeypatch.setattr(
        "app.services.research_join._validate_persisted_result",
        lambda *, stage, analysis_result: SimpleNamespace(
            evidence_quality=quality_by_stage[stage],
            limitations=[],
        ),
    )

    evaluation = inspect_research_join(
        db=_db_for_join(run=run, stage_runs=stages, results=results),
        analysis_run_id=run.id,
    )

    assert evaluation.gate.decision == ResearchGateDecision.ACCEPT
    assert evaluation.gate.can_proceed is True
    assert set(evaluation.results) == set(quality_by_stage)


def test_join_preserves_previous_success_when_retry_failed(monkeypatch):
    run = AnalysisRun(id=uuid4(), status=AnalysisRunStatus.RUNNING.value)
    market = _stage_run(run_id=run.id, stage=AnalysisStage.MARKET_RESEARCH)
    competitor_first = _stage_run(
        run_id=run.id,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
        attempt=1,
    )
    competitor_retry = _stage_run(
        run_id=run.id,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
        attempt=2,
        status=AnalysisStageStatus.FAILED,
    )
    customer = _stage_run(run_id=run.id, stage=AnalysisStage.CUSTOMER_INTELLIGENCE)
    stages = [market, competitor_first, competitor_retry, customer]
    results = [
        _analysis_result(market),
        _analysis_result(competitor_first),
        _analysis_result(customer),
    ]

    def fake_validate(*, stage, analysis_result):
        quality = {
            AnalysisStage.MARKET_RESEARCH: ResearchEvidenceQuality.STRONG,
            AnalysisStage.COMPETITOR_INTELLIGENCE: ResearchEvidenceQuality.WEAK,
            AnalysisStage.CUSTOMER_INTELLIGENCE: ResearchEvidenceQuality.INSUFFICIENT,
        }[stage]
        return SimpleNamespace(
            evidence_quality=quality,
            limitations=["gap"] if quality == ResearchEvidenceQuality.INSUFFICIENT else [],
        )

    monkeypatch.setattr(
        "app.services.research_join._validate_persisted_result",
        fake_validate,
    )

    evaluation = inspect_research_join(
        db=_db_for_join(run=run, stage_runs=stages, results=results),
        analysis_run_id=run.id,
    )

    assert evaluation.gate.decision == ResearchGateDecision.INSUFFICIENT
    assert evaluation.gate.can_proceed is True
    assert (
        evaluation.result_stage_run_ids[
            AnalysisStage.COMPETITOR_INTELLIGENCE
        ]
        == competitor_first.id
    )


def test_join_waits_for_running_latest_attempt():
    run = AnalysisRun(id=uuid4(), status=AnalysisRunStatus.RUNNING.value)
    stages = [
        _stage_run(run_id=run.id, stage=AnalysisStage.MARKET_RESEARCH),
        _stage_run(
            run_id=run.id,
            stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
            status=AnalysisStageStatus.RUNNING,
        ),
        _stage_run(run_id=run.id, stage=AnalysisStage.CUSTOMER_INTELLIGENCE),
    ]

    db = Mock(spec=Session)
    db.get.return_value = run
    db.scalars.return_value = _query_result(stages)

    with pytest.raises(ResearchJoinNotReadyError):
        inspect_research_join(
            db=db,
            analysis_run_id=run.id,
        )


def test_schedules_only_gate_retry_stage(monkeypatch):
    run_id = uuid4()
    stages = [
        _stage_run(run_id=run_id, stage=AnalysisStage.MARKET_RESEARCH),
        _stage_run(run_id=run_id, stage=AnalysisStage.COMPETITOR_INTELLIGENCE),
        _stage_run(run_id=run_id, stage=AnalysisStage.CUSTOMER_INTELLIGENCE),
    ]
    results = [_analysis_result(stage_run) for stage_run in stages]
    run = AnalysisRun(id=run_id, status=AnalysisRunStatus.RUNNING.value)
    quality_by_stage = {
        AnalysisStage.MARKET_RESEARCH: ResearchEvidenceQuality.STRONG,
        AnalysisStage.COMPETITOR_INTELLIGENCE: ResearchEvidenceQuality.WEAK,
        AnalysisStage.CUSTOMER_INTELLIGENCE: ResearchEvidenceQuality.MODERATE,
    }

    monkeypatch.setattr(
        "app.services.research_join._validate_persisted_result",
        lambda *, stage, analysis_result: SimpleNamespace(
            evidence_quality=quality_by_stage[stage],
            limitations=[],
        ),
    )

    evaluation = inspect_research_join(
        db=_db_for_join(run=run, stage_runs=stages, results=results),
        analysis_run_id=run.id,
    )

    db = Mock(spec=Session)
    competitor = stages[1]
    db.scalar.side_effect = [
        run,
        None,
        competitor,
    ]

    def assign_id(obj):
        if obj.id is None:
            obj.id = uuid4()

    db.add.side_effect = assign_id

    scheduled = schedule_targeted_retries(
        db=db,
        evaluation=evaluation,
    )

    assert len(scheduled) == 1
    assert scheduled[0].stage == AnalysisStage.COMPETITOR_INTELLIGENCE
    assert scheduled[0].attempt == 2
    retry = db.add.call_args.args[0]
    assert retry.stage == AnalysisStage.COMPETITOR_INTELLIGENCE.value
    assert retry.status == AnalysisStageStatus.PENDING.value
