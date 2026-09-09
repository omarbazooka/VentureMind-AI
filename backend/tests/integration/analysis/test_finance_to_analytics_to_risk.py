from collections.abc import Callable
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.finance.scenarios import calculate_financial_scenarios
from app.flows.business_analysis_flow import BusinessAnalysisFlow
from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioInputs,
    FinancialScenarioKind,
)
from app.schemas.research import ResearchEvidenceQuality
from app.schemas.risk import (
    RiskCategory,
    RiskDraft,
    RiskDraftAnalysis,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.analytics_executor import (
    execute_decision_analytics_stage,
)
from app.services.risk_executor import (
    RiskExecutionError,
    execute_risk_stage,
)


SessionFactory = Callable[[], Session]


@pytest.fixture
def integration_session_factory() -> SessionFactory:
    connection = engine.connect()
    transaction = connection.begin()

    def factory() -> Session:
        return Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

    try:
        yield factory
    finally:
        transaction.rollback()
        connection.close()


def _ready_snapshot() -> dict:
    return {
        "readiness": "READY_FOR_ANALYSIS",
        "profile_data": {
            "idea_description": "A SaaS platform for independent gyms.",
            "target_customers": ["Independent gym owners"],
            "target_country": "Egypt",
        },
        "profile_metadata": {},
        "unknown_fields": [],
    }


def _insufficient_research_result(stage: AnalysisStage) -> dict:
    result = {
        "summary": "Reliable evidence is currently insufficient for strong conclusions.",
        "findings": [],
        "evidence_sources": [],
        "evidence_quality": ResearchEvidenceQuality.INSUFFICIENT.value,
        "limitations": ["Reliable public evidence was insufficient."],
    }
    if stage == AnalysisStage.COMPETITOR_INTELLIGENCE:
        result["competitors"] = []
    return result


def _assumption(
    *,
    input_name: FinancialInputName,
    value: str,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        value=Decimal(value),
        provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale="Bounded integration-test assumption.",
    )


def _scenario(
    *,
    scenario: FinancialScenarioKind,
    price: str,
    volume: str,
    variable_cost: str,
    fixed_costs: str,
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=_assumption(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            value=price,
            currency="EGP",
            unit_label="customer",
        ),
        sales_volume=_assumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=volume,
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_assumption(
            input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
            value=variable_cost,
            currency="EGP",
            unit_label="customer",
        ),
        fixed_costs=_assumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=fixed_costs,
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        ),
    )


def _finance_bundle():
    return calculate_financial_scenarios(
        FinancialScenarioInputs(
            base=_scenario(
                scenario=FinancialScenarioKind.BASE,
                price="300",
                volume="100",
                variable_cost="100",
                fixed_costs="5000",
            ),
            upside=_scenario(
                scenario=FinancialScenarioKind.UPSIDE,
                price="350",
                volume="130",
                variable_cost="90",
                fixed_costs="5500",
            ),
            downside=_scenario(
                scenario=FinancialScenarioKind.DOWNSIDE,
                price="250",
                volume="70",
                variable_cost="120",
                fixed_costs="5000",
            ),
        )
    )


def _seed_completed_finance(
    *,
    session_factory: SessionFactory,
) -> tuple[UUID, UUID]:
    idea_id = uuid4()
    profile_id = uuid4()
    run_id = uuid4()
    snapshot = _ready_snapshot()

    with session_factory() as db:
        db.add(
            Idea(
                id=idea_id,
                title="Gym SaaS",
                raw_initial_idea="Software for independent gym owners.",
            )
        )
        db.flush()

        db.add(
            IdeaProfile(
                id=profile_id,
                idea_id=idea_id,
                version=1,
                readiness="READY_FOR_ANALYSIS",
                profile_data=snapshot["profile_data"],
                profile_metadata={},
                unknown_fields=[],
            )
        )
        db.flush()

        db.add(
            AnalysisRun(
                id=run_id,
                idea_id=idea_id,
                profile_id=profile_id,
                profile_version=1,
                profile_snapshot=snapshot,
                status=AnalysisRunStatus.RUNNING.value,
            )
        )
        db.flush()

        for stage in (
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        ):
            stage_run = AnalysisStageRun(
                id=uuid4(),
                analysis_run_id=run_id,
                stage=stage.value,
                attempt=1,
                status=AnalysisStageStatus.COMPLETED.value,
            )
            db.add(stage_run)
            db.flush()
            db.add(
                AnalysisResult(
                    id=uuid4(),
                    analysis_run_id=run_id,
                    stage_run_id=stage_run.id,
                    stage=stage.value,
                    result_data=_insufficient_research_result(stage),
                )
            )

        strategy_stage = AnalysisStageRun(
            id=uuid4(),
            analysis_run_id=run_id,
            stage=AnalysisStage.BUSINESS_STRATEGY.value,
            attempt=1,
            status=AnalysisStageStatus.COMPLETED.value,
        )
        db.add(strategy_stage)
        db.flush()
        db.add(
            AnalysisResult(
                id=uuid4(),
                analysis_run_id=run_id,
                stage_run_id=strategy_stage.id,
                stage=AnalysisStage.BUSINESS_STRATEGY.value,
                result_data=BusinessStrategyAnalysis(
                    executive_summary="Proceed to bounded financial and risk analysis.",
                    limitations=["Research evidence remains limited."],
                ).model_dump(mode="json"),
            )
        )

        finance_stage = AnalysisStageRun(
            id=uuid4(),
            analysis_run_id=run_id,
            stage=AnalysisStage.FINANCE.value,
            attempt=1,
            status=AnalysisStageStatus.COMPLETED.value,
        )
        db.add(finance_stage)
        db.flush()
        db.add(
            AnalysisResult(
                id=uuid4(),
                analysis_run_id=run_id,
                stage_run_id=finance_stage.id,
                stage=AnalysisStage.FINANCE.value,
                result_data=_finance_bundle().model_dump(mode="json"),
            )
        )
        db.commit()

    return run_id, finance_stage.id


def _execute_analytics(
    *,
    session_factory: SessionFactory,
    run_id: UUID,
) -> UUID:
    with session_factory() as db:
        stage = BusinessAnalysisFlow().advance_finance(
            db=db,
            run_id=run_id,
        )
        stage_id = stage.id
        db.commit()

    result = execute_decision_analytics_stage(
        session_factory=session_factory,
        stage_run_id=stage_id,
    )
    assert result.stage == AnalysisStage.DECISION_ANALYTICS.value
    return stage_id


def _schedule_risk(
    *,
    session_factory: SessionFactory,
    run_id: UUID,
) -> UUID:
    with session_factory() as db:
        stage = BusinessAnalysisFlow().advance_analytics(
            db=db,
            run_id=run_id,
        )
        stage_id = stage.id
        db.commit()
    return stage_id


def _groundable_risk_draft() -> RiskDraftAnalysis:
    return RiskDraftAnalysis(
        executive_summary="Financial sensitivity is the main modeled risk.",
        risks=[
            RiskDraft(
                category=RiskCategory.FINANCIAL,
                title="Operating-result sensitivity",
                statement="Profitability is sensitive to changes in core operating assumptions.",
                likelihood=RiskLikelihood.MEDIUM,
                impact=RiskImpact.HIGH,
                confidence=0.85,
                rationale="Finance and Decision Analytics show material operating-result sensitivity.",
                mitigation_actions=["Validate pricing and cost assumptions before scaling."],
                monitoring_signals=["Track realized operating margin versus BASE."],
                supporting_stages=[
                    AnalysisStage.FINANCE,
                    AnalysisStage.DECISION_ANALYTICS,
                ],
                financial_metrics=[FinancialMetricName.OPERATING_RESULT],
                decision_kpis=[],
                sensitivity_inputs=[FinancialInputName.SELLING_PRICE_PER_UNIT],
            )
        ],
    )


def test_completed_finance_flows_through_analytics_and_risk(
    integration_session_factory,
):
    session_factory = integration_session_factory
    run_id, finance_stage_id = _seed_completed_finance(
        session_factory=session_factory,
    )
    analytics_stage_id = _execute_analytics(
        session_factory=session_factory,
        run_id=run_id,
    )

    with session_factory() as db:
        analytics_stage = db.get(
            AnalysisStageRun,
            analytics_stage_id,
        )
        assert analytics_stage is not None
        assert analytics_stage.status == AnalysisStageStatus.COMPLETED.value

        analytics_result = db.scalar(
            select(AnalysisResult).where(
                AnalysisResult.stage_run_id == analytics_stage_id
            )
        )
        assert analytics_result is not None
        parsed = DecisionAnalyticsResult.model_validate(
            analytics_result.result_data
        )
        assert parsed.finance_stage_run_id == finance_stage_id
        assert parsed.sensitivity is not None

    risk_stage_id = _schedule_risk(
        session_factory=session_factory,
        run_id=run_id,
    )
    captured_contexts = []

    def risk_runner(context):
        captured_contexts.append(context)
        return _groundable_risk_draft()

    persisted_risk = execute_risk_stage(
        session_factory=session_factory,
        stage_run_id=risk_stage_id,
        runner=risk_runner,
    )

    assert len(captured_contexts) == 1
    assert captured_contexts[0].finance_stage_run_id == finance_stage_id
    assert captured_contexts[0].analytics_stage_run_id == analytics_stage_id

    with session_factory() as db:
        risk_stage = db.get(
            AnalysisStageRun,
            risk_stage_id,
        )
        assert risk_stage is not None
        assert risk_stage.status == AnalysisStageStatus.COMPLETED.value
        assert risk_stage.started_at is not None
        assert risk_stage.completed_at is not None

        result = db.get(AnalysisResult, persisted_risk.id)
        assert result is not None
        assert result.stage == AnalysisStage.RISK.value
        assert result.result_data["overall_level"] == RiskLevel.HIGH.value
        assert result.result_data["risks"][0]["risk_score"] == 6
        assert any(
            "INSUFFICIENT_EVIDENCE" in limitation
            for limitation in result.result_data["limitations"]
        )


def test_hallucinated_risk_lineage_fails_without_persisted_result(
    integration_session_factory,
):
    session_factory = integration_session_factory
    run_id, _ = _seed_completed_finance(
        session_factory=session_factory,
    )
    _execute_analytics(
        session_factory=session_factory,
        run_id=run_id,
    )
    risk_stage_id = _schedule_risk(
        session_factory=session_factory,
        run_id=run_id,
    )

    def invalid_runner(context):
        return RiskDraftAnalysis(
            executive_summary="Invalid draft lineage.",
            risks=[
                RiskDraft(
                    category=RiskCategory.EXECUTION,
                    title="Invented profile dependency",
                    statement="This draft cites a profile field that does not exist.",
                    likelihood=RiskLikelihood.MEDIUM,
                    impact=RiskImpact.MEDIUM,
                    confidence=0.5,
                    rationale="Intentional integration failure case.",
                    profile_fields=["invented_profile_field"],
                )
            ],
        )

    with pytest.raises(RiskExecutionError):
        execute_risk_stage(
            session_factory=session_factory,
            stage_run_id=risk_stage_id,
            runner=invalid_runner,
        )

    with session_factory() as db:
        risk_stage = db.get(
            AnalysisStageRun,
            risk_stage_id,
        )
        assert risk_stage is not None
        assert risk_stage.status == AnalysisStageStatus.FAILED.value
        assert risk_stage.error_code == "INVALID_RISK_GROUNDING"

        persisted = db.scalar(
            select(AnalysisResult).where(
                AnalysisResult.stage_run_id == risk_stage_id
            )
        )
        assert persisted is None
