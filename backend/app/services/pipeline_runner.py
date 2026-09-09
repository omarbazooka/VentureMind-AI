from collections.abc import Callable
from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.flows.business_analysis_flow import BusinessAnalysisFlow
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance_runtime import FinanceExecutionStatus
from app.services.analytics_executor import execute_decision_analytics_stage
from app.services.business_strategy_executor import execute_business_strategy_stage
from app.services.competitor_intelligence_executor import (
    execute_competitor_intelligence_stage,
)
from app.services.customer_intelligence_executor import (
    execute_customer_intelligence_stage,
)
from app.services.decision_executor import execute_decision_stage
from app.services.finance_executor import execute_finance_stage
from app.services.market_research_executor import execute_market_research_stage
from app.services.report_generator import generate_structured_report
from app.services.risk_executor import execute_risk_stage
from app.services.validation_executor import execute_validation_stage

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]
DefaultSessionFactory = SessionLocal


def _default_market_runner() -> Any:
    from app.crews.market_research.runtime import build_market_research_runner

    return build_market_research_runner()


def _default_competitor_runner() -> Any:
    from app.crews.competitor_intelligence.runtime import (
        build_competitor_intelligence_runner,
    )

    return build_competitor_intelligence_runner()


def _default_customer_runner() -> Any:
    from app.crews.customer_intelligence.runtime import (
        build_customer_intelligence_runner,
    )

    return build_customer_intelligence_runner()


def _default_strategy_runner() -> Any:
    from app.crews.business_strategy.runtime import build_business_strategy_runner

    return build_business_strategy_runner()


def _default_finance_runner() -> Any:
    from app.finance.assumption_builder import FinanceAssumptionBuilder
    from app.llm.gateway import LLMGateway

    return FinanceAssumptionBuilder(llm_gateway=LLMGateway())


def _default_risk_runner() -> Any:
    from app.crews.risk.runtime import build_risk_runner

    return build_risk_runner()


def _default_validation_runner() -> Any:
    from app.crews.validation.runtime import build_validation_runner

    return build_validation_runner()


def _default_decision_runner() -> Any:
    from app.crews.decision.runtime import build_decision_runner

    return build_decision_runner()


class PipelineExecutionError(RuntimeError):
    pass


class PipelineRunner:
    """Orchestrates end-to-end stage execution for an AnalysisRun."""

    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        market_runner_factory: Callable[[], Any] | None = None,
        competitor_runner_factory: Callable[[], Any] | None = None,
        customer_runner_factory: Callable[[], Any] | None = None,
        strategy_runner_factory: Callable[[], Any] | None = None,
        finance_runner_factory: Callable[[], Any] | None = None,
        risk_runner_factory: Callable[[], Any] | None = None,
        validation_runner_factory: Callable[[], Any] | None = None,
        decision_runner_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.session_factory = session_factory or DefaultSessionFactory
        self._market_runner_factory = market_runner_factory or _default_market_runner
        self._competitor_runner_factory = (
            competitor_runner_factory or _default_competitor_runner
        )
        self._customer_runner_factory = (
            customer_runner_factory or _default_customer_runner
        )
        self._strategy_runner_factory = (
            strategy_runner_factory or _default_strategy_runner
        )
        self._finance_runner_factory = (
            finance_runner_factory or _default_finance_runner
        )
        self._risk_runner_factory = risk_runner_factory or _default_risk_runner
        self._validation_runner_factory = (
            validation_runner_factory or _default_validation_runner
        )
        self._decision_runner_factory = (
            decision_runner_factory or _default_decision_runner
        )
        self._flow = BusinessAnalysisFlow()

    def _get_latest_stage_run(
        self,
        analysis_run_id: UUID,
        stage: AnalysisStage,
    ) -> AnalysisStageRun | None:
        with self.session_factory() as db:
            return db.scalar(
                select(AnalysisStageRun)
                .where(
                    AnalysisStageRun.analysis_run_id == analysis_run_id,
                    AnalysisStageRun.stage == stage.value,
                )
                .order_by(AnalysisStageRun.attempt.desc())
                .limit(1)
            )

    def _mark_run_failed(
        self,
        analysis_run_id: UUID,
        error_code: str,
        error_message: str,
    ) -> None:
        with self.session_factory() as db:
            run = db.get(AnalysisRun, analysis_run_id)
            if run is not None:
                run.status = AnalysisRunStatus.FAILED.value
                run.error_code = error_code
                run.error_message = error_message
                run.completed_at = datetime.now(timezone.utc)
                db.commit()

    def run(self, analysis_run_id: UUID) -> AnalysisRunStatus:
        """Run the analysis pipeline sequentially until completion or pause."""
        logger.info(
            "Starting pipeline execution for analysis_run %s",
            analysis_run_id,
        )

        try:
            # 1. Start research if run is QUEUED.
            with self.session_factory() as db:
                run = db.get(AnalysisRun, analysis_run_id)
                if run is None:
                    raise PipelineExecutionError(
                        f"AnalysisRun {analysis_run_id} not found"
                    )

                if run.status in (
                    AnalysisRunStatus.COMPLETED.value,
                    AnalysisRunStatus.FAILED.value,
                ):
                    logger.info(
                        "AnalysisRun %s is already in terminal state %s",
                        analysis_run_id,
                        run.status,
                    )
                    return AnalysisRunStatus(run.status)

                if run.status == AnalysisRunStatus.QUEUED.value:
                    self._flow.initialize(db=db, run_id=analysis_run_id)
                    db.commit()

            # 2. Execute initial research stages. The Job Fair runner keeps this
            # sequential for now; the architecture can execute the three research
            # branches in parallel once durable worker execution is introduced.
            for stage, runner_factory, executor in (
                (
                    AnalysisStage.MARKET_RESEARCH,
                    self._market_runner_factory,
                    execute_market_research_stage,
                ),
                (
                    AnalysisStage.COMPETITOR_INTELLIGENCE,
                    self._competitor_runner_factory,
                    execute_competitor_intelligence_stage,
                ),
                (
                    AnalysisStage.CUSTOMER_INTELLIGENCE,
                    self._customer_runner_factory,
                    execute_customer_intelligence_stage,
                ),
            ):
                stage_run = self._get_latest_stage_run(analysis_run_id, stage)
                if stage_run is None:
                    raise PipelineExecutionError(
                        f"Missing stage run for {stage.value}"
                    )

                if stage_run.status != AnalysisStageStatus.COMPLETED.value:
                    logger.info(
                        "Executing stage %s for run %s",
                        stage.value,
                        analysis_run_id,
                    )
                    executor(
                        session_factory=self.session_factory,
                        stage_run_id=stage_run.id,
                        runner=runner_factory(),
                    )

            # 3. Advance research / Evidence Gate checkpoint.
            max_gate_cycles = 3
            gate_cycle = 0
            while gate_cycle < max_gate_cycles:
                gate_cycle += 1
                with self.session_factory() as db:
                    step = self._flow.advance_research(
                        db=db,
                        run_id=analysis_run_id,
                    )
                    db.commit()

                if step.scheduled_retries:
                    logger.info(
                        "Evidence gate scheduled %d retries on cycle %d",
                        len(step.scheduled_retries),
                        gate_cycle,
                    )
                    for retry in step.scheduled_retries:
                        if retry.stage == AnalysisStage.MARKET_RESEARCH:
                            execute_market_research_stage(
                                session_factory=self.session_factory,
                                stage_run_id=retry.stage_run_id,
                                runner=self._market_runner_factory(),
                            )
                        elif retry.stage == AnalysisStage.COMPETITOR_INTELLIGENCE:
                            execute_competitor_intelligence_stage(
                                session_factory=self.session_factory,
                                stage_run_id=retry.stage_run_id,
                                runner=self._competitor_runner_factory(),
                            )
                        elif retry.stage == AnalysisStage.CUSTOMER_INTELLIGENCE:
                            execute_customer_intelligence_stage(
                                session_factory=self.session_factory,
                                stage_run_id=retry.stage_run_id,
                                runner=self._customer_runner_factory(),
                            )
                    continue

                if not step.evaluation.gate.can_proceed:
                    self._mark_run_failed(
                        analysis_run_id=analysis_run_id,
                        error_code="EVIDENCE_GATE_FAILED",
                        error_message=(
                            "Evidence gate rejected research evidence and "
                            "max retries were exceeded."
                        ),
                    )
                    return AnalysisRunStatus.FAILED

                break

            # 4. Business Strategy.
            strategy_stage_run = self._get_latest_stage_run(
                analysis_run_id,
                AnalysisStage.BUSINESS_STRATEGY,
            )
            if strategy_stage_run is None:
                raise PipelineExecutionError(
                    "Strategy stage run not scheduled after research gate"
                )

            if strategy_stage_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Business Strategy for run %s",
                    analysis_run_id,
                )
                execute_business_strategy_stage(
                    session_factory=self.session_factory,
                    stage_run_id=strategy_stage_run.id,
                    runner=self._strategy_runner_factory(),
                )

            # 5. Finance.
            with self.session_factory() as db:
                finance_stage_run = self._flow.advance_strategy(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            if finance_stage_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Finance stage for run %s",
                    analysis_run_id,
                )
                outcome = execute_finance_stage(
                    session_factory=self.session_factory,
                    stage_run_id=finance_stage_run.id,
                    assumption_runner=self._finance_runner_factory(),
                )
                if outcome.status == FinanceExecutionStatus.PAUSED_FOR_USER:
                    logger.info(
                        "Analysis run %s paused for user input (input_id: %s)",
                        analysis_run_id,
                        outcome.run_input_id,
                    )
                    return AnalysisRunStatus.PAUSED_FOR_USER

            # 6. Decision Analytics.
            with self.session_factory() as db:
                analytics_stage_run = self._flow.advance_finance(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            if analytics_stage_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Decision Analytics for run %s",
                    analysis_run_id,
                )
                execute_decision_analytics_stage(
                    session_factory=self.session_factory,
                    stage_run_id=analytics_stage_run.id,
                )

            # 7. Risk.
            with self.session_factory() as db:
                risk_stage_run = self._flow.advance_analytics(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            if risk_stage_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Risk analysis for run %s",
                    analysis_run_id,
                )
                execute_risk_stage(
                    session_factory=self.session_factory,
                    stage_run_id=risk_stage_run.id,
                    runner=self._risk_runner_factory(),
                )

            # 8. Independent Validation.
            with self.session_factory() as db:
                validation_stage_run = self._flow.advance_risk(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            if validation_stage_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Independent Validation for run %s",
                    analysis_run_id,
                )
                execute_validation_stage(
                    session_factory=self.session_factory,
                    stage_run_id=validation_stage_run.id,
                    runner=self._validation_runner_factory(),
                )

            # 9. Day 9 Validation is a gate only. It may identify affected
            # stages, but it must not schedule direct upstream retries. Day 12's
            # deterministic dependency resolver owns invalidation/re-analysis.
            with self.session_factory() as db:
                decision_run = self._flow.advance_validation(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            if (
                decision_run is None
                or decision_run.stage
                != AnalysisStage.INVESTMENT_COMMITTEE.value
            ):
                raise PipelineExecutionError(
                    "Validation did not produce the Investment Committee stage; "
                    "direct validation retries are not allowed in this pipeline"
                )

            # 10. Investment Committee / Final Decision.
            if decision_run.status != AnalysisStageStatus.COMPLETED.value:
                logger.info(
                    "Executing Final Decision stage for run %s",
                    analysis_run_id,
                )
                execute_decision_stage(
                    session_factory=self.session_factory,
                    stage_run_id=decision_run.id,
                    runner=self._decision_runner_factory(),
                )

            with self.session_factory() as db:
                self._flow.advance_decision(
                    db=db,
                    run_id=analysis_run_id,
                )
                db.commit()

            # 11. Compile authoritative Structured Report and complete the run.
            logger.info(
                "Compiling Structured Report for run %s",
                analysis_run_id,
            )
            with self.session_factory() as db:
                generate_structured_report(
                    db=db,
                    analysis_run_id=analysis_run_id,
                )
                run = db.get(AnalysisRun, analysis_run_id)
                if run is not None:
                    run.status = AnalysisRunStatus.COMPLETED.value
                    run.completed_at = datetime.now(timezone.utc)
                    run.error_code = None
                    run.error_message = None
                db.commit()

            logger.info(
                "Pipeline completed successfully for run %s",
                analysis_run_id,
            )
            return AnalysisRunStatus.COMPLETED

        except Exception as exc:
            logger.exception(
                "Pipeline execution failed for run %s: %s",
                analysis_run_id,
                exc,
            )
            self._mark_run_failed(
                analysis_run_id=analysis_run_id,
                error_code="PIPELINE_ERROR",
                error_message=str(exc),
            )
            return AnalysisRunStatus.FAILED


def run_pipeline_sync(
    analysis_run_id: UUID,
    session_factory: SessionFactory | None = None,
) -> AnalysisRunStatus:
    """Convenience entrypoint to execute the pipeline synchronously."""
    runner = PipelineRunner(session_factory=session_factory)
    return runner.run(analysis_run_id=analysis_run_id)
