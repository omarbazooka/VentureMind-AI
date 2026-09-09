from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.schemas.finance import FinancialScenarioBundle
from app.schemas.risk import RiskAnalysis
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis
from app.services.research_join import (
    ResearchJoinError,
    inspect_research_join,
)


class DecisionContextError(RuntimeError):
    pass


class DecisionContextDependencyError(DecisionContextError):
    pass


def _load_completed_stage_result(
    *,
    db: Session,
    analysis_run_id: UUID,
    stage: AnalysisStage,
) -> AnalysisResult:
    statement = (
        select(AnalysisResult)
        .join(
            AnalysisStageRun,
            AnalysisStageRun.id == AnalysisResult.stage_run_id,
        )
        .where(
            AnalysisResult.analysis_run_id == analysis_run_id,
            AnalysisResult.stage == stage.value,
            AnalysisStageRun.stage == stage.value,
            AnalysisStageRun.status == AnalysisStageStatus.COMPLETED.value,
        )
        .order_by(
            AnalysisStageRun.attempt.desc(),
            AnalysisResult.created_at.desc(),
        )
    )
    result = db.scalar(statement)

    if result is None:
        raise DecisionContextDependencyError(
            f"Decision context requires a completed {stage.value} result"
        )

    return result


def build_investment_committee_context(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> InvestmentCommitteeContext:
    analysis_run = db.get(AnalysisRun, analysis_run_id)
    if analysis_run is None:
        raise DecisionContextDependencyError(
            "Parent AnalysisRun was not found"
        )

    try:
        snapshot = AnalysisProfileSnapshot.model_validate(
            analysis_run.profile_snapshot
        )
    except ValidationError as exc:
        raise DecisionContextDependencyError(
            "Parent AnalysisRun contains an invalid profile snapshot"
        ) from exc

    try:
        research_evaluation = inspect_research_join(
            db=db,
            analysis_run_id=analysis_run_id,
        )
    except ResearchJoinError as exc:
        raise DecisionContextDependencyError(
            "Decision context cannot load research because Research Join is not ready"
        ) from exc

    strategy_result = _load_completed_stage_result(
        db=db,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.BUSINESS_STRATEGY,
    )
    finance_result = _load_completed_stage_result(
        db=db,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.FINANCE,
    )
    analytics_result = _load_completed_stage_result(
        db=db,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.DECISION_ANALYTICS,
    )
    risk_result = _load_completed_stage_result(
        db=db,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.RISK,
    )
    validation_result = _load_completed_stage_result(
        db=db,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.INDEPENDENT_VALIDATION,
    )

    try:
        strategy_analysis = BusinessStrategyAnalysis.model_validate(
            strategy_result.result_data
        )
        finance_bundle = FinancialScenarioBundle.model_validate(
            finance_result.result_data
        )
        analytics_analysis = DecisionAnalyticsResult.model_validate(
            analytics_result.result_data
        )
        risk_analysis = RiskAnalysis.model_validate(
            risk_result.result_data
        )
        validation_analysis = ValidationAnalysis.model_validate(
            validation_result.result_data
        )
    except ValidationError as exc:
        raise DecisionContextDependencyError(
            "An upstream stage result contains invalid data"
        ) from exc

    return InvestmentCommitteeContext(
        profile_snapshot=snapshot,
        research_gate=research_evaluation.gate,
        market_analysis=research_evaluation.results.get(
            AnalysisStage.MARKET_RESEARCH
        ),
        competitor_analysis=research_evaluation.results.get(
            AnalysisStage.COMPETITOR_INTELLIGENCE
        ),
        customer_analysis=research_evaluation.results.get(
            AnalysisStage.CUSTOMER_INTELLIGENCE
        ),
        business_strategy_stage_run_id=strategy_result.stage_run_id,
        business_strategy=strategy_analysis,
        finance_stage_run_id=finance_result.stage_run_id,
        finance_bundle=finance_bundle,
        analytics_stage_run_id=analytics_result.stage_run_id,
        decision_analytics=analytics_analysis,
        risk_stage_run_id=risk_result.stage_run_id,
        risk_analysis=risk_analysis,
        validation_stage_run_id=validation_result.stage_run_id,
        validation_analysis=validation_analysis,
    )
