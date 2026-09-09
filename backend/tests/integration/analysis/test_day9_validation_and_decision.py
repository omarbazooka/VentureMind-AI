from collections.abc import Callable
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.finance.scenarios import (
    calculate_financial_scenarios,
    FinancialScenarioInputs,
)
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
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)
from app.schemas.research import (
    EvidenceProvenance,
    MarketAnalysis,
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.risk import RiskAnalysis, RiskLevel
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import (
    ValidationDraft,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStatus,
)
from app.services.decision_executor import execute_decision_stage
from app.services.validation_executor import (
    ValidationExecutionError,
    execute_validation_stage,
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


def _setup_analysis_pipeline(db: Session):
    idea = Idea(
        title="B2B AI Copilot",
        raw_initial_idea="AI workflow automation",
        state="READY_FOR_ANALYSIS",
    )
    db.add(idea)
    db.flush()

    profile = IdeaProfile(
        idea_id=idea.id,
        version=1,
        readiness="READY_FOR_ANALYSIS",
        profile_data={"problem": "High manual operational costs", "target_customer": "SMEs"},
        profile_metadata={},
        unknown_fields=[],
    )
    db.add(profile)
    db.flush()

    run = AnalysisRun(
        idea_id=idea.id,
        profile_id=profile.id,
        profile_version=profile.version,
        profile_snapshot={
            "readiness": "READY_FOR_ANALYSIS",
            "profile_data": profile.profile_data,
            "profile_metadata": {},
            "unknown_fields": [],
        },
        status=AnalysisRunStatus.RUNNING.value,
    )
    db.add(run)
    db.flush()

    # Create research stages & results
    source = ResearchEvidenceSource(
        source_id="src-mkt-1",
        title="Market Report 2026",
        provenance=EvidenceProvenance.WEB,
        url="https://example.com/market",
    )
    mkt_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.MARKET_RESEARCH.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    comp_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    cust_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    db.add_all([mkt_stage, comp_stage, cust_stage])
    db.flush()

    mkt_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=mkt_stage.id,
        stage=AnalysisStage.MARKET_RESEARCH.value,
        result_data=MarketAnalysis(
            summary="Strong B2B market",
            findings=[],
            evidence_sources=[source],
            evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            limitations=["Limited sampling"],
        ).model_dump(mode="json"),
    )
    db.add(mkt_result)

    comp_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=comp_stage.id,
        stage=AnalysisStage.COMPETITOR_INTELLIGENCE.value,
        result_data={
            "summary": "Reliable competitor evidence is currently insufficient.",
            "competitors": [],
            "evidence_sources": [],
            "evidence_quality": ResearchEvidenceQuality.INSUFFICIENT.value,
            "limitations": ["Limited public competitor data."],
        },
    )
    db.add(comp_result)

    cust_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=cust_stage.id,
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE.value,
        result_data={
            "summary": "Reliable customer evidence is currently insufficient.",
            "evidence_sources": [],
            "evidence_quality": ResearchEvidenceQuality.INSUFFICIENT.value,
            "limitations": ["Limited survey reach."],
        },
    )
    db.add(cust_result)

    # Strategy
    strat_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.BUSINESS_STRATEGY.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    db.add(strat_stage)
    db.flush()
    strat_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=strat_stage.id,
        stage=AnalysisStage.BUSINESS_STRATEGY.value,
        result_data=BusinessStrategyAnalysis(
            executive_summary="Target SME niche with land-and-expand model"
        ).model_dump(mode="json"),
    )
    db.add(strat_result)

    # Finance
    fin_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.FINANCE.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    db.add(fin_stage)
    db.flush()

    def _make_assumptions(scen: FinancialScenarioKind) -> FinancialAssumptionSet:
        return FinancialAssumptionSet(
            scenario=scen,
            selling_price_per_unit=FinancialAssumption(
                input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
                value=Decimal("500.0"),
                currency="USD",
                unit_label="customer",
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Pricing model",
            ),
            sales_volume=FinancialAssumption(
                input_name=FinancialInputName.SALES_VOLUME,
                value=Decimal("100.0"),
                unit_label="customer",
                period=FinancialPeriod.MONTHLY,
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Target volume",
            ),
            variable_cost_per_unit=FinancialAssumption(
                input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
                value=Decimal("50.0"),
                currency="USD",
                unit_label="customer",
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Unit hosting cost",
            ),
            fixed_costs=FinancialAssumption(
                input_name=FinancialInputName.FIXED_COSTS,
                value=Decimal("5000.0"),
                currency="USD",
                period=FinancialPeriod.MONTHLY,
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Core team & tools",
            ),
        )

    fin_bundle = calculate_financial_scenarios(
        FinancialScenarioInputs(
            base=_make_assumptions(FinancialScenarioKind.BASE),
            upside=_make_assumptions(FinancialScenarioKind.UPSIDE),
            downside=_make_assumptions(FinancialScenarioKind.DOWNSIDE),
        )
    )
    fin_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=fin_stage.id,
        stage=AnalysisStage.FINANCE.value,
        result_data=fin_bundle.model_dump(mode="json"),
    )
    db.add(fin_result)

    # Decision Analytics
    da_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    db.add(da_stage)
    db.flush()
    da_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=da_stage.id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
        result_data=DecisionAnalyticsResult(
            finance_stage_run_id=fin_stage.id,
            kpis=[],
        ).model_dump(mode="json"),
    )
    db.add(da_result)

    # Risk
    risk_stage = AnalysisStageRun(
        analysis_run_id=run.id,
        stage=AnalysisStage.RISK.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    db.add(risk_stage)
    db.flush()
    risk_result = AnalysisResult(
        analysis_run_id=run.id,
        stage_run_id=risk_stage.id,
        stage=AnalysisStage.RISK.value,
        result_data=RiskAnalysis(
            executive_summary="Moderate market adoption risk",
            risks=[],
            overall_level=None,
            limitations=[],
        ).model_dump(mode="json"),
    )
    db.add(risk_result)
    db.flush()

    return run.id


def test_full_day9_flow_integration(integration_session_factory: SessionFactory):
    with integration_session_factory() as db:
        run_id = _setup_analysis_pipeline(db)
        db.commit()

    # Step 1: Risk completed -> Advance schedules Independent Validation
    flow = BusinessAnalysisFlow()
    with integration_session_factory() as db:
        val_stage_run = flow.advance_risk(db=db, run_id=run_id)
        db.commit()
        val_stage_id = val_stage_run.id

    assert val_stage_run.stage == AnalysisStage.INDEPENDENT_VALIDATION.value
    assert val_stage_run.status == AnalysisStageStatus.PENDING.value

    # Step 2: Execute Independent Validation
    def fake_validator(context):
        return ValidationDraft(
            executive_assessment="Thoroughly challenged and validated assumptions.",
            issues=[
                ValidationIssue(
                    category=ValidationIssueCategory.UNREFLECTED_RISK,
                    severity=ValidationSeverity.LOW,
                    description="Minor risk noted in Strategy not fully reflected.",
                    affected_stages=[AnalysisStage.RISK],
                    evidence_ids=["src-mkt-1"],
                )
            ],
            limitations=["Limited regional market data"],
        )

    val_res = execute_validation_stage(
        session_factory=integration_session_factory,
        stage_run_id=val_stage_id,
        runner=fake_validator,
    )
    assert val_res.id is not None

    # Step 3: Advance Validation -> Schedules Investment Committee
    with integration_session_factory() as db:
        val_db_res = db.get(AnalysisResult, val_res.id)
        assert val_db_res is not None
        assert val_db_res.stage == AnalysisStage.INDEPENDENT_VALIDATION.value
        assert val_db_res.result_data["status"] == ValidationStatus.INSUFFICIENT_EVIDENCE.value

        dec_stage_run = flow.advance_validation(db=db, run_id=run_id)
        db.commit()
        dec_stage_id = dec_stage_run.id

    assert dec_stage_run.stage == AnalysisStage.INVESTMENT_COMMITTEE.value
    assert dec_stage_run.status == AnalysisStageStatus.PENDING.value

    # Step 4: Execute Investment Committee
    def fake_committee(context):
        return FinalDecisionDraft(
            decision=VentureDecision.CONDITIONAL_GO,
            confidence=DecisionConfidence.MEDIUM,
            rationale="Solid unit economics with manageable initial risk.",
            supporting_evidence_lineage=["MARKET_RESEARCH", "FINANCE"],
            strongest_positive_signals=["Strong gross margins", "Clear SME pain point"],
            strongest_negative_signals=["High sales cycle length"],
            critical_assumptions=["Fixed costs do not scale prematurely"],
            limitations=["Pilot phase required"],
            what_could_change=["Sales conversion drops below 5%"],
            recommended_next_steps=["Launch paid beta with 5 design partners"],
        )

    dec_res = execute_decision_stage(
        session_factory=integration_session_factory,
        stage_run_id=dec_stage_id,
        runner=fake_committee,
    )
    assert dec_res.id is not None

    # Step 5: Advance Decision -> Verifies pipeline completed ready for report
    with integration_session_factory() as db:
        dec_db_res = db.get(AnalysisResult, dec_res.id)
        assert dec_db_res is not None
        assert dec_db_res.stage == AnalysisStage.INVESTMENT_COMMITTEE.value
        assert dec_db_res.result_data["decision"] == VentureDecision.CONDITIONAL_GO.value

        final_result = flow.advance_decision(db=db, run_id=run_id)
        assert final_result.id == dec_res.id


def test_validation_rejects_hallucinated_evidence_in_integration(integration_session_factory: SessionFactory):
    with integration_session_factory() as db:
        run_id = _setup_analysis_pipeline(db)
        val_stage_run = BusinessAnalysisFlow().advance_risk(db=db, run_id=run_id)
        db.commit()
        val_stage_id = val_stage_run.id

    def hallucinated_validator(context):
        return ValidationDraft(
            executive_assessment="Fake citation included.",
            issues=[
                ValidationIssue(
                    category=ValidationIssueCategory.UNSUPPORTED_CLAIM,
                    severity=ValidationSeverity.MEDIUM,
                    description="Citing non-existent paper.",
                    affected_stages=[AnalysisStage.MARKET_RESEARCH],
                    evidence_ids=["fake-non-existent-src-999"],
                )
            ],
        )

    with pytest.raises(ValidationExecutionError, match="Validation grounding verification failed"):
        execute_validation_stage(
            session_factory=integration_session_factory,
            stage_run_id=val_stage_id,
            runner=hallucinated_validator,
        )

    # Verify stage failed and no result was persisted
    with integration_session_factory() as db:
        stage = db.get(AnalysisStageRun, val_stage_id)
        assert stage.status == AnalysisStageStatus.FAILED.value
        assert stage.error_code == "INVALID_VALIDATION_GROUNDING"

        result = db.scalar(select(AnalysisResult).where(AnalysisResult.stage_run_id == val_stage_id))
        assert result is None
