from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from pydantic import ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.analysis_run_input import AnalysisRunInput
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.report import Report
from app.schemas.analysis import (
    AnalysisProgressResponse,
    AnalysisRunCreateResponse,
    AnalysisRunInputStatus,
    AnalysisRunStatus,
    AnalysisStageStatus,
    AnswerInputRequest,
    AnswerInputResponse,
    PendingInputSummary,
    StageProgressItem,
)
from app.schemas.finance import FinancialInputName, FinancialPeriod
from app.schemas.finance_runtime import (
    FinanceUserAnswerMode,
    FinanceUserInputAnswer,
)
from app.schemas.report import StructuredReport
from app.schemas.report_action import (
    ReportActionRequest,
    ReportActionResponse,
)
from app.services.analysis_run import (
    AnalysisIdeaNotFoundError,
    AnalysisProfileNotFoundError,
    AnalysisProfileNotReadyError,
    AnalysisRunAlreadyActiveError,
    start_analysis_run,
)
from app.services.finance_stage import (
    FinanceStageStateError,
    answer_finance_user_input,
)
from app.services.pipeline_runner import run_pipeline_sync
from app.services.report_action_handler import handle_report_action


router = APIRouter(
    prefix="/ideas",
    tags=["analysis"],
)

DbSession = Annotated[
    Session,
    Depends(get_db),
]


@router.post(
    "/{idea_id}/analysis",
    response_model=AnalysisRunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    idea_id: UUID,
    db: DbSession,
    background_tasks: BackgroundTasks,
) -> AnalysisRunCreateResponse:
    try:
        analysis_run = start_analysis_run(
            db=db,
            idea_id=idea_id,
        )
    except AnalysisIdeaNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        ) from exc
    except AnalysisProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea profile not found",
        ) from exc
    except AnalysisProfileNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Idea profile is not ready for analysis",
                **exc.readiness_result.model_dump(mode="json"),
            },
        ) from exc
    except AnalysisRunAlreadyActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "An analysis run is already active for this idea",
                "run_id": str(exc.analysis_run.id),
                "status": exc.analysis_run.status,
            },
        ) from exc

    db.commit()
    db.refresh(analysis_run)

    background_tasks.add_task(run_pipeline_sync, analysis_run.id)

    return AnalysisRunCreateResponse(
        run_id=analysis_run.id,
        idea_id=analysis_run.idea_id,
        profile_id=analysis_run.profile_id,
        profile_version=analysis_run.profile_version,
        status=analysis_run.status,
        created_at=analysis_run.created_at,
    )


@router.get(
    "/{idea_id}/analysis/progress",
    response_model=AnalysisProgressResponse,
)
def get_analysis_progress(
    idea_id: UUID,
    db: DbSession,
) -> AnalysisProgressResponse:
    idea = db.get(Idea, idea_id)
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )

    run = db.scalar(
        select(AnalysisRun)
        .where(AnalysisRun.idea_id == idea_id)
        .order_by(desc(AnalysisRun.created_at))
        .limit(1)
    )

    if run is None:
        return AnalysisProgressResponse(
            idea_id=idea_id,
            run_status="NOT_STARTED",
        )

    stage_runs = list(
        db.scalars(
            select(AnalysisStageRun)
            .where(AnalysisStageRun.analysis_run_id == run.id)
            .order_by(AnalysisStageRun.created_at.asc())
        ).all()
    )

    completed_stages = [
        stage_run.stage
        for stage_run in stage_runs
        if stage_run.status == AnalysisStageStatus.COMPLETED.value
    ]

    # Report a stage that is actually active before falling back to queued work.
    # This avoids showing a later PENDING stage while an earlier stage is RUNNING.
    current_stage = None
    for active_status in (
        AnalysisStageStatus.PAUSED_FOR_USER.value,
        AnalysisStageStatus.RUNNING.value,
        AnalysisStageStatus.PENDING.value,
    ):
        current_stage_run = next(
            (
                stage_run
                for stage_run in stage_runs
                if stage_run.status == active_status
            ),
            None,
        )
        if current_stage_run is not None:
            current_stage = current_stage_run.stage
            break

    pending_input_summary = None
    if run.status == AnalysisRunStatus.PAUSED_FOR_USER.value:
        pending_input = db.scalar(
            select(AnalysisRunInput)
            .where(
                AnalysisRunInput.analysis_run_id == run.id,
                AnalysisRunInput.status == AnalysisRunInputStatus.PENDING.value,
            )
            .order_by(desc(AnalysisRunInput.created_at))
            .limit(1)
        )
        if pending_input is not None:
            request_data = pending_input.request_data or {}
            pending_input_summary = PendingInputSummary(
                input_id=pending_input.id,
                stage_run_id=pending_input.stage_run_id,
                input_name=pending_input.input_name,
                question=request_data.get(
                    "question",
                    f"Input required for {pending_input.input_name}",
                ),
                options=request_data.get("options", []),
                allow_custom=request_data.get("allow_custom", True),
                currency=request_data.get("currency"),
                unit_label=request_data.get("unit_label"),
                period=request_data.get("period"),
            )

    latest_report = db.scalar(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )

    return AnalysisProgressResponse(
        idea_id=idea_id,
        analysis_run_id=run.id,
        run_status=run.status,
        current_stage=current_stage,
        completed_stages=list(dict.fromkeys(completed_stages)),
        stage_runs=[
            StageProgressItem(
                stage=stage_run.stage,
                attempt=stage_run.attempt,
                status=stage_run.status,
                started_at=stage_run.started_at,
                completed_at=stage_run.completed_at,
                error_code=stage_run.error_code,
                error_message=stage_run.error_message,
            )
            for stage_run in stage_runs
        ],
        pending_input=pending_input_summary,
        has_report=latest_report is not None,
        report_version=(latest_report.version if latest_report else None),
        error_code=run.error_code,
        error_message=run.error_message,
    )


@router.get(
    "/{idea_id}/analysis/inputs/pending",
    response_model=PendingInputSummary,
)
def get_pending_input(
    idea_id: UUID,
    db: DbSession,
) -> PendingInputSummary:
    run = db.scalar(
        select(AnalysisRun)
        .where(
            AnalysisRun.idea_id == idea_id,
            AnalysisRun.status == AnalysisRunStatus.PAUSED_FOR_USER.value,
        )
        .order_by(desc(AnalysisRun.created_at))
        .limit(1)
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No paused analysis run requiring input for this idea",
        )

    pending_input = db.scalar(
        select(AnalysisRunInput)
        .where(
            AnalysisRunInput.analysis_run_id == run.id,
            AnalysisRunInput.status == AnalysisRunInputStatus.PENDING.value,
        )
        .order_by(desc(AnalysisRunInput.created_at))
        .limit(1)
    )
    if pending_input is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending input found for this analysis run",
        )

    request_data = pending_input.request_data or {}
    return PendingInputSummary(
        input_id=pending_input.id,
        stage_run_id=pending_input.stage_run_id,
        input_name=pending_input.input_name,
        question=request_data.get(
            "question",
            f"Input required for {pending_input.input_name}",
        ),
        options=request_data.get("options", []),
        allow_custom=request_data.get("allow_custom", True),
        currency=request_data.get("currency"),
        unit_label=request_data.get("unit_label"),
        period=request_data.get("period"),
    )


@router.post(
    "/{idea_id}/analysis/inputs/{input_id}/answer",
    response_model=AnswerInputResponse,
)
def answer_analysis_input(
    idea_id: UUID,
    input_id: UUID,
    body: AnswerInputRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
) -> AnswerInputResponse:
    run_input = db.get(AnalysisRunInput, input_id)
    if run_input is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis input not found",
        )

    analysis_run = db.get(AnalysisRun, run_input.analysis_run_id)
    if analysis_run is None or analysis_run.idea_id != idea_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis input does not belong to this idea",
        )

    if run_input.status != AnalysisRunInputStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Input is not in PENDING state",
        )

    if (body.choice is None) == (body.value is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide exactly one of choice or value",
        )

    try:
        input_name = FinancialInputName(run_input.input_name)
        period = FinancialPeriod(body.period) if body.period else None

        if body.choice is not None:
            answer = FinanceUserInputAnswer(
                input_name=input_name,
                answer_mode=FinanceUserAnswerMode.SELECTED_OPTION,
                selected_option_id=body.choice,
            )
        else:
            answer = FinanceUserInputAnswer(
                input_name=input_name,
                answer_mode=FinanceUserAnswerMode.CUSTOM,
                value=body.value,
                currency=body.currency,
                unit_label=body.unit_label,
                period=period,
            )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid Finance input answer: {exc}",
        ) from exc

    try:
        answer_finance_user_input(
            db=db,
            run_input_id=input_id,
            answer=answer,
            source_message_id=body.source_message_id,
        )
    except FinanceStageStateError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    db.commit()
    background_tasks.add_task(run_pipeline_sync, run_input.analysis_run_id)

    return AnswerInputResponse(
        input_id=input_id,
        status="ANSWERED",
        analysis_run_status="RUNNING",
        message="Input accepted; analysis resumed in background",
    )


@router.get(
    "/{idea_id}/report/latest",
    response_model=StructuredReport,
)
def get_latest_report(
    idea_id: UUID,
    db: DbSession,
) -> StructuredReport:
    report = db.scalar(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this idea",
        )
    return StructuredReport.model_validate(report.report_data)


@router.get(
    "/{idea_id}/reports",
)
def list_reports(
    idea_id: UUID,
    db: DbSession,
) -> list[dict[str, Any]]:
    reports = db.scalars(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
    ).all()
    return [
        {
            "id": str(report.id),
            "idea_id": str(report.idea_id),
            "analysis_run_id": str(report.analysis_run_id),
            "version": report.version,
            "created_at": report.created_at,
        }
        for report in reports
    ]


@router.get(
    "/{idea_id}/reports/{version}",
    response_model=StructuredReport,
)
def get_report_version(
    idea_id: UUID,
    version: int,
    db: DbSession,
) -> StructuredReport:
    report = db.scalar(
        select(Report).where(
            Report.idea_id == idea_id,
            Report.version == version,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report version {version} not found for this idea",
        )
    return StructuredReport.model_validate(report.report_data)


@router.post(
    "/{idea_id}/report/action",
    response_model=ReportActionResponse,
)
def execute_report_action(
    idea_id: UUID,
    request: ReportActionRequest,
    db: DbSession,
) -> ReportActionResponse:
    report_record = db.scalar(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    if report_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this idea",
        )
    structured_report = StructuredReport.model_validate(
        report_record.report_data
    )
    return handle_report_action(
        report=structured_report,
        request=request,
    )
