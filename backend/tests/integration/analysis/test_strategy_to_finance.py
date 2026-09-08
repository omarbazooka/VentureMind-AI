from collections.abc import Callable
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
)
from app.models.analysis_result import (
    AnalysisResult,
)
from app.models.analysis_run import (
    AnalysisRun,
)
from app.models.analysis_run_input import (
    AnalysisRunInput,
)
from app.models.analysis_stage_run import (
    AnalysisStageRun,
)
from app.models.idea import Idea
from app.models.idea_profile import (
    IdeaProfile,
)
from app.schemas.analysis import (
    AnalysisRunInputStatus,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import (
    FinancialAssumptionProvenance,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)
from app.schemas.finance_ai import (
    FinancialAssumptionDraft,
    FinancialAssumptionDraftBundle,
    FinancialScenarioAssumptionDraft,
)
from app.schemas.finance_runtime import (
    FinanceExecutionStatus,
    FinanceUserAnswerMode,
    FinanceUserInputAnswer,
)
from app.schemas.research import (
    ResearchEvidenceQuality,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)
from app.services.finance_executor import (
    execute_finance_stage,
)
from app.services.finance_stage import (
    answer_finance_user_input,
)


SessionFactory = Callable[
    [],
    Session,
]


@pytest.fixture
def integration_session_factory(
) -> SessionFactory:
    connection = engine.connect()
    transaction = connection.begin()

    def factory() -> Session:
        return Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode=(
                "create_savepoint"
            ),
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
            "idea_description": (
                "A SaaS platform for independent gyms."
            ),
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        "profile_metadata": {},
        "unknown_fields": [],
    }


def _insufficient_research_result(
    stage: AnalysisStage,
) -> dict:
    result = {
        "summary": (
            "Reliable evidence is currently "
            "insufficient for strong conclusions."
        ),
        "findings": [],
        "evidence_sources": [],
        "evidence_quality": (
            ResearchEvidenceQuality
            .INSUFFICIENT
            .value
        ),
        "limitations": [
            "Reliable public evidence was insufficient."
        ],
    }

    if (
        stage
        == AnalysisStage.COMPETITOR_INTELLIGENCE
    ):
        result["competitors"] = []

    return result


def _strategy_result() -> BusinessStrategyAnalysis:
    return BusinessStrategyAnalysis(
        executive_summary=(
            "The venture can proceed to bounded "
            "financial modeling, while research "
            "limitations remain explicit."
        ),
        limitations=[
            "Public research evidence remains limited."
        ],
        finance_questions=[
            "What selling price should Finance evaluate?"
        ],
    )


def _seed_completed_strategy(
    *,
    session_factory: SessionFactory,
) -> UUID:
    idea_id = uuid4()
    profile_id = uuid4()
    run_id = uuid4()
    snapshot = _ready_snapshot()

    with session_factory() as db:
        idea = Idea(
            id=idea_id,
            title="Gym SaaS",
            raw_initial_idea=(
                "Software for independent gym owners."
            ),
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            id=profile_id,
            idea_id=idea_id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data=snapshot["profile_data"],
            profile_metadata={},
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        analysis_run = AnalysisRun(
            id=run_id,
            idea_id=idea_id,
            profile_id=profile_id,
            profile_version=1,
            profile_snapshot=snapshot,
            status=AnalysisRunStatus.RUNNING.value,
        )
        db.add(analysis_run)
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
                status=(
                    AnalysisStageStatus
                    .COMPLETED
                    .value
                ),
            )
            db.add(stage_run)
            db.flush()

            db.add(
                AnalysisResult(
                    id=uuid4(),
                    analysis_run_id=run_id,
                    stage_run_id=stage_run.id,
                    stage=stage.value,
                    result_data=(
                        _insufficient_research_result(
                            stage
                        )
                    ),
                )
            )

        strategy_stage = AnalysisStageRun(
            id=uuid4(),
            analysis_run_id=run_id,
            stage=(
                AnalysisStage
                .BUSINESS_STRATEGY
                .value
            ),
            attempt=1,
            status=(
                AnalysisStageStatus
                .COMPLETED
                .value
            ),
        )
        db.add(strategy_stage)
        db.flush()

        db.add(
            AnalysisResult(
                id=uuid4(),
                analysis_run_id=run_id,
                stage_run_id=strategy_stage.id,
                stage=(
                    AnalysisStage
                    .BUSINESS_STRATEGY
                    .value
                ),
                result_data=(
                    _strategy_result()
                    .model_dump(mode="json")
                ),
            )
        )

        db.commit()

    return run_id


def _known_draft(
    *,
    input_name: FinancialInputName,
    value: str,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumptionDraft:
    return FinancialAssumptionDraft(
        input_name=input_name,
        value=Decimal(value),
        provenance=(
            FinancialAssumptionProvenance
            .AI_ASSUMPTION
        ),
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale=(
            "Bounded test assumption for Finance "
            "integration coverage."
        ),
    )


def _unknown_price_draft(
) -> FinancialAssumptionDraft:
    return FinancialAssumptionDraft(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        value=None,
        provenance=None,
        currency="EGP",
        unit_label="customer",
        rationale=(
            "Selling price requires an explicit "
            "user decision."
        ),
    )


def _scenario_draft(
    *,
    scenario: FinancialScenarioKind,
    price: str | None,
    volume: str,
    variable_cost: str,
    fixed_costs: str,
) -> FinancialScenarioAssumptionDraft:
    price_draft = (
        _unknown_price_draft()
        if price is None
        else _known_draft(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=price,
            currency="EGP",
            unit_label="customer",
        )
    )

    return FinancialScenarioAssumptionDraft(
        scenario=scenario,
        selling_price_per_unit=price_draft,
        sales_volume=_known_draft(
            input_name=(
                FinancialInputName.SALES_VOLUME
            ),
            value=volume,
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_known_draft(
            input_name=(
                FinancialInputName
                .VARIABLE_COST_PER_UNIT
            ),
            value=variable_cost,
            currency="EGP",
            unit_label="customer",
        ),
        fixed_costs=_known_draft(
            input_name=(
                FinancialInputName.FIXED_COSTS
            ),
            value=fixed_costs,
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        ),
    )


def _ready_finance_drafts(
) -> FinancialAssumptionDraftBundle:
    return FinancialAssumptionDraftBundle(
        base=_scenario_draft(
            scenario=FinancialScenarioKind.BASE,
            price="300",
            volume="100",
            variable_cost="100",
            fixed_costs="5000",
        ),
        upside=_scenario_draft(
            scenario=FinancialScenarioKind.UPSIDE,
            price="350",
            volume="130",
            variable_cost="90",
            fixed_costs="5500",
        ),
        downside=_scenario_draft(
            scenario=FinancialScenarioKind.DOWNSIDE,
            price="250",
            volume="70",
            variable_cost="120",
            fixed_costs="5000",
        ),
    )


def _missing_price_drafts(
) -> FinancialAssumptionDraftBundle:
    return FinancialAssumptionDraftBundle(
        base=_scenario_draft(
            scenario=FinancialScenarioKind.BASE,
            price=None,
            volume="100",
            variable_cost="100",
            fixed_costs="5000",
        ),
        upside=_scenario_draft(
            scenario=FinancialScenarioKind.UPSIDE,
            price=None,
            volume="130",
            variable_cost="90",
            fixed_costs="5500",
        ),
        downside=_scenario_draft(
            scenario=FinancialScenarioKind.DOWNSIDE,
            price=None,
            volume="70",
            variable_cost="120",
            fixed_costs="5000",
        ),
    )


def _schedule_finance(
    *,
    session_factory: SessionFactory,
    run_id: UUID,
) -> UUID:
    with session_factory() as db:
        finance_stage = (
            BusinessAnalysisFlow()
            .advance_strategy(
                db=db,
                run_id=run_id,
            )
        )
        finance_stage_id = finance_stage.id
        db.commit()

    return finance_stage_id


def test_strategy_to_finance_completes_ready_model(
    integration_session_factory,
):
    session_factory = integration_session_factory
    run_id = _seed_completed_strategy(
        session_factory=session_factory,
    )
    finance_stage_id = _schedule_finance(
        session_factory=session_factory,
        run_id=run_id,
    )

    captured_contexts = []

    def assumption_runner(context):
        captured_contexts.append(context)
        return _ready_finance_drafts()

    outcome = execute_finance_stage(
        session_factory=session_factory,
        stage_run_id=finance_stage_id,
        assumption_runner=assumption_runner,
    )

    assert (
        outcome.status
        == FinanceExecutionStatus.COMPLETED
    )
    assert outcome.result_id is not None
    assert len(captured_contexts) == 1
    assert (
        captured_contexts[0]
        .business_strategy
        .executive_summary
        == _strategy_result().executive_summary
    )

    with session_factory() as db:
        stage_run = db.get(
            AnalysisStageRun,
            finance_stage_id,
        )
        assert stage_run is not None
        assert (
            stage_run.status
            == AnalysisStageStatus.COMPLETED.value
        )
        assert stage_run.started_at is not None
        assert stage_run.completed_at is not None

        result = db.get(
            AnalysisResult,
            outcome.result_id,
        )
        assert result is not None
        assert result.stage == AnalysisStage.FINANCE.value
        assert (
            result.result_data["base"]
            ["assumptions"]
            ["selling_price_per_unit"]
            ["value"]
            == "300"
        )

        analysis_run = db.get(
            AnalysisRun,
            run_id,
        )
        assert analysis_run is not None
        assert (
            analysis_run.status
            == AnalysisRunStatus.RUNNING.value
        )


def test_finance_pause_answer_reclaim_and_complete(
    integration_session_factory,
):
    session_factory = integration_session_factory
    run_id = _seed_completed_strategy(
        session_factory=session_factory,
    )
    finance_stage_id = _schedule_finance(
        session_factory=session_factory,
        run_id=run_id,
    )

    first_outcome = execute_finance_stage(
        session_factory=session_factory,
        stage_run_id=finance_stage_id,
        assumption_runner=(
            lambda context: _missing_price_drafts()
        ),
    )

    assert (
        first_outcome.status
        == FinanceExecutionStatus.PAUSED_FOR_USER
    )
    assert first_outcome.run_input_id is not None
    assert first_outcome.request is not None
    assert (
        first_outcome.request.input_name
        == FinancialInputName.SELLING_PRICE_PER_UNIT
    )
    assert first_outcome.request.currency == "EGP"
    assert first_outcome.request.unit_label == "customer"

    with session_factory() as db:
        paused_stage = db.get(
            AnalysisStageRun,
            finance_stage_id,
        )
        paused_run = db.get(
            AnalysisRun,
            run_id,
        )
        pending_input = db.get(
            AnalysisRunInput,
            first_outcome.run_input_id,
        )

        assert paused_stage is not None
        assert paused_run is not None
        assert pending_input is not None
        assert (
            paused_stage.status
            == AnalysisStageStatus
            .PAUSED_FOR_USER
            .value
        )
        assert (
            paused_run.status
            == AnalysisRunStatus
            .PAUSED_FOR_USER
            .value
        )
        assert (
            pending_input.status
            == AnalysisRunInputStatus.PENDING.value
        )

    with session_factory() as db:
        answered = answer_finance_user_input(
            db=db,
            run_input_id=(
                first_outcome.run_input_id
            ),
            answer=FinanceUserInputAnswer(
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                answer_mode=(
                    FinanceUserAnswerMode.CUSTOM
                ),
                value=Decimal("325"),
                currency="EGP",
                unit_label="customer",
            ),
        )
        db.commit()

        assert (
            answered.status
            == AnalysisRunInputStatus.ANSWERED.value
        )

    with session_factory() as db:
        resumed_stage = db.get(
            AnalysisStageRun,
            finance_stage_id,
        )
        resumed_run = db.get(
            AnalysisRun,
            run_id,
        )

        assert resumed_stage is not None
        assert resumed_run is not None
        assert (
            resumed_stage.status
            == AnalysisStageStatus.PENDING.value
        )
        assert (
            resumed_run.status
            == AnalysisRunStatus.RUNNING.value
        )

    second_outcome = execute_finance_stage(
        session_factory=session_factory,
        stage_run_id=finance_stage_id,
        assumption_runner=(
            lambda context: _missing_price_drafts()
        ),
    )

    assert (
        second_outcome.status
        == FinanceExecutionStatus.COMPLETED
    )
    assert second_outcome.result_id is not None

    with session_factory() as db:
        completed_stage = db.get(
            AnalysisStageRun,
            finance_stage_id,
        )
        result = db.get(
            AnalysisResult,
            second_outcome.result_id,
        )
        answered_input = db.get(
            AnalysisRunInput,
            first_outcome.run_input_id,
        )

        assert completed_stage is not None
        assert result is not None
        assert answered_input is not None
        assert (
            completed_stage.status
            == AnalysisStageStatus.COMPLETED.value
        )
        assert (
            answered_input.status
            == AnalysisRunInputStatus.ANSWERED.value
        )

        base_price = (
            result.result_data["base"]
            ["assumptions"]
            ["selling_price_per_unit"]
        )

        assert base_price["value"] == "325"
        assert (
            base_price["provenance"]
            == FinancialAssumptionProvenance.USER.value
        )
        assert (
            base_price["analysis_run_input_ids"]
            == [
                str(first_outcome.run_input_id)
            ]
        )
