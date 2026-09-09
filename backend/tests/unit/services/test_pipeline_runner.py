from collections.abc import Callable
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.models.report import Report
from app.research.competitor_evidence import CompetitorAnalysisDraft
from app.research.customer_evidence import CustomerAnalysisDraft
from app.research.market_evidence import MarketAnalysisDraft
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionDraft,
    VentureDecision,
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
from app.schemas.finance import FinancialMetricName
from app.schemas.research import ResearchEvidenceQuality
from app.schemas.risk import (
    RiskCategory,
    RiskDraft,
    RiskDraftAnalysis,
    RiskImpact,
    RiskLikelihood,
)
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import (
    ValidationDraft,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
)
from app.services.pipeline_runner import PipelineRunner

SessionFactory = Callable[[], Session]


@pytest.fixture
def test_session_factory() -> SessionFactory:
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


def _make_assumption(
    input_name: FinancialInputName,
    value: Decimal | None,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
    provenance: FinancialAssumptionProvenance = FinancialAssumptionProvenance.AI_ASSUMPTION,
    profile_fields: list[str] | None = None,
) -> FinancialAssumptionDraft:
    if value is not None:
        return FinancialAssumptionDraft(
            input_name=input_name,
            value=value,
            currency=currency,
            unit_label=unit_label,
            period=period,
            provenance=provenance,
            profile_fields=profile_fields or [],
            supporting_stages=[],
            evidence_source_ids=[],
            rationale="Tested input assumption",
        )
    return FinancialAssumptionDraft(
        input_name=input_name,
        value=None,
        currency=None,
        unit_label=None,
        period=None,
        provenance=None,
        profile_fields=[],
        supporting_stages=[],
        evidence_source_ids=[],
        rationale="Unknown assumption requiring user input",
    )


def _complete_scenario_draft(kind: FinancialScenarioKind) -> FinancialScenarioAssumptionDraft:
    return FinancialScenarioAssumptionDraft(
        scenario=kind,
        selling_price_per_unit=_make_assumption(
            FinancialInputName.SELLING_PRICE_PER_UNIT,
            Decimal("50.00"),
            currency="USD",
            unit_label="seat",
        ),
        sales_volume=_make_assumption(
            FinancialInputName.SALES_VOLUME,
            Decimal("100"),
            unit_label="seat",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_make_assumption(
            FinancialInputName.VARIABLE_COST_PER_UNIT,
            Decimal("10.00"),
            currency="USD",
            unit_label="seat",
        ),
        fixed_costs=_make_assumption(
            FinancialInputName.FIXED_COSTS,
            Decimal("1500.00"),
            currency="USD",
            period=FinancialPeriod.MONTHLY,
        ),
        starting_cash=_make_assumption(
            FinancialInputName.STARTING_CASH,
            Decimal("20000.00"),
            currency="USD",
            provenance=FinancialAssumptionProvenance.USER,
            profile_fields=["starting_cash"],
        ),
    )


def _paused_scenario_draft(kind: FinancialScenarioKind) -> FinancialScenarioAssumptionDraft:
    # Selling price missing -> triggers pause for user input
    return FinancialScenarioAssumptionDraft(
        scenario=kind,
        selling_price_per_unit=_make_assumption(
            FinancialInputName.SELLING_PRICE_PER_UNIT, None
        ),
        sales_volume=_make_assumption(
            FinancialInputName.SALES_VOLUME,
            Decimal("100"),
            unit_label="seat",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_make_assumption(
            FinancialInputName.VARIABLE_COST_PER_UNIT,
            Decimal("10.00"),
            currency="USD",
            unit_label="seat",
        ),
        fixed_costs=_make_assumption(
            FinancialInputName.FIXED_COSTS,
            Decimal("1500.00"),
            currency="USD",
            period=FinancialPeriod.MONTHLY,
        ),
        starting_cash=_make_assumption(
            FinancialInputName.STARTING_CASH,
            Decimal("20000.00"),
            currency="USD",
            provenance=FinancialAssumptionProvenance.USER,
            profile_fields=["starting_cash"],
        ),
    )


def test_pipeline_runner_full_run(test_session_factory: SessionFactory):
    # Setup idea and profile in DB
    with test_session_factory() as db:
        idea = Idea(
            title="AutoCare AI",
            raw_initial_idea="Predictive maintenance for vehicles",
        )
        db.add(idea)
        db.flush()

        p_data = {
            "idea_description": "Predictive maintenance software.",
            "target_customers": ["Auto repair shops"],
            "target_country": "US",
            "starting_cash": "20000",
        }
        p_meta = {
            "idea_description": {"provenance": "USER"},
            "target_customers": {"provenance": "USER"},
            "target_country": {"provenance": "USER"},
            "starting_cash": {"provenance": "USER"},
        }

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data=p_data,
            profile_metadata=p_meta,
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={
                "readiness": "READY_FOR_ANALYSIS",
                "profile_data": p_data,
                "profile_metadata": p_meta,
                "unknown_fields": [],
            },
            status=AnalysisRunStatus.QUEUED.value,
        )
        db.add(run)
        db.commit()
        run_id = run.id

    # Mock runners
    def fake_market_runner():
        return lambda claim: MarketAnalysisDraft(
            summary="Strong market growth signal.",
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Early market stage"],
        )

    def fake_competitor_runner():
        return lambda claim: CompetitorAnalysisDraft(
            summary="Fragmented competition.",
            competitors=[],
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Limited public pricing"],
        )

    def fake_customer_runner():
        return lambda claim: CustomerAnalysisDraft(
            summary="Repair shops actively seeking fleet management.",
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Regional sampling only"],
        )

    def fake_strategy_runner():
        return lambda claim: BusinessStrategyAnalysis(
            executive_summary="Solid strategy targeting independent auto shops.",
            positioning=[],
            value_proposition=[],
            business_model_implications=[],
            go_to_market=[],
            strategic_strengths=[],
            strategic_weaknesses=[],
            critical_assumptions=[],
            finance_questions=["Exact bay count distribution"],
            limitations=["Limited public pricing evidence requires ongoing validation"],
        )

    def fake_finance_runner():
        return lambda context: FinancialAssumptionDraftBundle(
            base=_complete_scenario_draft(FinancialScenarioKind.BASE),
            upside=_complete_scenario_draft(FinancialScenarioKind.UPSIDE),
            downside=_complete_scenario_draft(FinancialScenarioKind.DOWNSIDE),
        )

    def fake_risk_runner():
        return lambda claim: RiskDraftAnalysis(
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

    def fake_validation_runner():
        return lambda claim: ValidationDraft(
            executive_assessment="All stages grounded and verified.",
            issues=[],
            limitations=[],
        )

    def fake_decision_runner():
        return lambda claim: FinalDecisionDraft(
            decision=VentureDecision.GO,
            confidence=DecisionConfidence.HIGH,
            rationale="Validated business model with viable unit economics.",
            supporting_evidence_lineage=["FINANCE", "BUSINESS_STRATEGY"],
            strongest_positive_signals=["High recurring margin"],
            strongest_negative_signals=[],
            critical_assumptions=[],
            limitations=[],
            what_could_change=[],
            recommended_next_steps=[],
        )

    runner = PipelineRunner(
        session_factory=test_session_factory,
        market_runner_factory=fake_market_runner,
        competitor_runner_factory=fake_competitor_runner,
        customer_runner_factory=fake_customer_runner,
        strategy_runner_factory=fake_strategy_runner,
        finance_runner_factory=fake_finance_runner,
        risk_runner_factory=fake_risk_runner,
        validation_runner_factory=fake_validation_runner,
        decision_runner_factory=fake_decision_runner,
    )

    final_status = runner.run(analysis_run_id=run_id)
    assert final_status == AnalysisRunStatus.COMPLETED

    # Verify run and report in database
    with test_session_factory() as db:
        saved_run = db.get(AnalysisRun, run_id)
        assert saved_run.status == AnalysisRunStatus.COMPLETED.value
        assert saved_run.completed_at is not None

        # Check all stages completed
        stages = list(
            db.scalars(
                select(AnalysisStageRun)
                .where(AnalysisStageRun.analysis_run_id == run_id)
            ).all()
        )
        completed_stages = {s.stage for s in stages if s.status == AnalysisStageStatus.COMPLETED.value}
        assert AnalysisStage.MARKET_RESEARCH.value in completed_stages
        assert AnalysisStage.COMPETITOR_INTELLIGENCE.value in completed_stages
        assert AnalysisStage.CUSTOMER_INTELLIGENCE.value in completed_stages
        assert AnalysisStage.BUSINESS_STRATEGY.value in completed_stages
        assert AnalysisStage.FINANCE.value in completed_stages
        assert AnalysisStage.DECISION_ANALYTICS.value in completed_stages
        assert AnalysisStage.RISK.value in completed_stages
        assert AnalysisStage.INDEPENDENT_VALIDATION.value in completed_stages
        assert AnalysisStage.INVESTMENT_COMMITTEE.value in completed_stages

        # Check Report was created
        report = db.scalar(select(Report).where(Report.analysis_run_id == run_id))
        assert report is not None
        assert report.version == 1
        assert report.report_data["executive_summary"] is not None


def test_pipeline_runner_pauses_for_user(test_session_factory: SessionFactory):
    # Setup idea and profile in DB
    with test_session_factory() as db:
        idea = Idea(
            title="CareDesk AI",
            raw_initial_idea="Clinic intake workflow",
        )
        db.add(idea)
        db.flush()

        p_data = {
            "idea_description": "Clinic intake workflow automation.",
            "target_customers": ["Dental clinics"],
            "target_country": "US",
            "starting_cash": "20000",
        }
        p_meta = {
            "idea_description": {"provenance": "USER"},
            "target_customers": {"provenance": "USER"},
            "target_country": {"provenance": "USER"},
            "starting_cash": {"provenance": "USER"},
        }

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data=p_data,
            profile_metadata=p_meta,
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={
                "readiness": "READY_FOR_ANALYSIS",
                "profile_data": p_data,
                "profile_metadata": p_meta,
                "unknown_fields": [],
            },
            status=AnalysisRunStatus.QUEUED.value,
        )
        db.add(run)
        db.commit()
        run_id = run.id

    def fake_market_runner():
        return lambda claim: MarketAnalysisDraft(
            summary="Market evidence.",
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Limited public pricing evidence"],
        )

    def fake_competitor_runner():
        return lambda claim: CompetitorAnalysisDraft(
            summary="Competitor evidence.",
            competitors=[],
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Limited competitor pricing transparency"],
        )

    def fake_customer_runner():
        return lambda claim: CustomerAnalysisDraft(
            summary="Customer evidence.",
            findings=[],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Limited regional clinic survey data"],
        )

    def fake_strategy_runner():
        return lambda claim: BusinessStrategyAnalysis(
            executive_summary="Solid strategy targeting dental clinics.",
            positioning=[],
            value_proposition=[],
            business_model_implications=[],
            go_to_market=[],
            strategic_strengths=[],
            strategic_weaknesses=[],
            critical_assumptions=[],
            finance_questions=["Unclear monthly price per clinic"],
            limitations=["Limited public pricing evidence requires ongoing validation"],
        )

    def fake_paused_finance_runner():
        return lambda context: FinancialAssumptionDraftBundle(
            base=_paused_scenario_draft(FinancialScenarioKind.BASE),
            upside=_paused_scenario_draft(FinancialScenarioKind.UPSIDE),
            downside=_paused_scenario_draft(FinancialScenarioKind.DOWNSIDE),
        )

    runner = PipelineRunner(
        session_factory=test_session_factory,
        market_runner_factory=fake_market_runner,
        competitor_runner_factory=fake_competitor_runner,
        customer_runner_factory=fake_customer_runner,
        strategy_runner_factory=fake_strategy_runner,
        finance_runner_factory=fake_paused_finance_runner,
    )

    final_status = runner.run(analysis_run_id=run_id)
    assert final_status == AnalysisRunStatus.PAUSED_FOR_USER

    with test_session_factory() as db:
        saved_run = db.get(AnalysisRun, run_id)
        assert saved_run.status == AnalysisRunStatus.PAUSED_FOR_USER.value
