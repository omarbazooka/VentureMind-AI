from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.finance.scenarios import calculate_financial_scenarios
from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.schemas.analysis import AnalysisStage, AnalysisStageStatus
from app.schemas.analytics import DecisionAnalyticsResult, DecisionKPI, DecisionKPIName
from app.schemas.decision import (
    DECISION_UPSTREAM_STAGES,
    DecisionConfidence,
    FinalDecisionAnalysis,
    VentureDecision,
)
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
from app.schemas.report import ReportMetricStatus, StructuredReport
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    EvidenceProvenance,
    MarketAnalysis,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
)
from app.schemas.risk import (
    GroundedRisk,
    RiskAnalysis,
    RiskCategory,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis, ValidationStatus
from app.services.report_generator import ReportGenerationError, generate_structured_report


def _assumptions(scenario: FinancialScenarioKind) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=FinancialAssumption(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            value=Decimal("200"),
            currency="USD",
            unit_label="seat",
            provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
            rationale="Explicit modeling assumption",
        ),
        sales_volume=FinancialAssumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=Decimal("50"),
            unit_label="seat",
            period=FinancialPeriod.MONTHLY,
            provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
            rationale="Explicit modeling assumption",
        ),
        variable_cost_per_unit=FinancialAssumption(
            input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
            value=Decimal("20"),
            currency="USD",
            unit_label="seat",
            provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
            rationale="Explicit modeling assumption",
        ),
        fixed_costs=FinancialAssumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=Decimal("4000"),
            currency="USD",
            period=FinancialPeriod.MONTHLY,
            provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
            rationale="Explicit modeling assumption",
        ),
    )


def _mock_db_with_exact_lineage(missing_stage: AnalysisStage | None = None):
    idea_id = uuid4()
    run_id = uuid4()
    stage_ids = {stage: uuid4() for stage in DECISION_UPSTREAM_STAGES}

    idea = Idea(
        id=idea_id,
        title="SaaS Automation",
        raw_initial_idea="Automate workflows for SMEs",
    )
    run = AnalysisRun(
        id=run_id,
        idea_id=idea_id,
        profile_id=uuid4(),
        profile_version=1,
        profile_snapshot={"profile_data": {"industry": "B2B SaaS"}},
        status="RUNNING",
    )

    source = ResearchEvidenceSource(
        source_id="src-1",
        title="Industry Report",
        provenance=EvidenceProvenance.WEB,
        url="https://example.com/data",
    )
    market = MarketAnalysis(
        summary="Large B2B market",
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Limited regional data"],
    )
    competitors = CompetitorAnalysis(
        summary="Fragmented competition",
        competitors=[],
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Limited public competitor evidence"],
    )
    customer = CustomerAnalysis(
        summary="Customer evidence remains limited",
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Early evidence only"],
    )
    strategy = BusinessStrategyAnalysis(
        executive_summary="Direct sales into a focused SME segment"
    )
    finance = calculate_financial_scenarios(
        FinancialScenarioInputs(
            base=_assumptions(FinancialScenarioKind.BASE),
            upside=_assumptions(FinancialScenarioKind.UPSIDE),
            downside=_assumptions(FinancialScenarioKind.DOWNSIDE),
        )
    )
    analytics = DecisionAnalyticsResult(
        finance_stage_run_id=stage_ids[AnalysisStage.FINANCE],
        kpis=[
            DecisionKPI(
                metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
                scenario=FinancialScenarioKind.BASE,
                value=Decimal("50"),
                formula="operating_result / revenue * 100",
                source_financial_metrics=[
                    FinancialMetricName.OPERATING_RESULT,
                    FinancialMetricName.REVENUE,
                ],
            )
        ],
    )
    risk = RiskAnalysis(
        executive_summary="Manageable financial risk",
        risks=[
            GroundedRisk(
                category=RiskCategory.FINANCIAL,
                title="Cash burn before break-even",
                statement="Runway can tighten if acquisition is slower than modeled.",
                likelihood=RiskLikelihood.MEDIUM,
                impact=RiskImpact.MEDIUM,
                confidence=0.8,
                rationale="The modeled outcome depends on customer volume.",
                risk_score=4,
                risk_level=RiskLevel.MEDIUM,
                mitigation_actions=["Keep fixed overhead controlled"],
                monitoring_signals=["Monthly acquired customers"],
                supporting_stages=[AnalysisStage.FINANCE],
                financial_metrics=[FinancialMetricName.OPERATING_RESULT],
            )
        ],
        overall_level=RiskLevel.MEDIUM,
    )

    validation_lineage = {
        stage: stage_id
        for stage, stage_id in stage_ids.items()
        if stage != AnalysisStage.INDEPENDENT_VALIDATION
    }
    validation = ValidationAnalysis(
        status=ValidationStatus.PASSED,
        can_proceed=True,
        executive_assessment="Validated packet is internally consistent.",
        upstream_stage_run_ids=validation_lineage,
    )
    decision = FinalDecisionAnalysis(
        decision=VentureDecision.CONDITIONAL_GO,
        confidence=DecisionConfidence.MEDIUM,
        rationale="The validated packet supports a bounded paid pilot.",
        strongest_positive_signals=["Positive modeled operating result"],
        strongest_negative_signals=["Evidence remains limited"],
        critical_assumptions=["Modeled customer volume is achieved"],
        limitations=["Direct demand evidence is limited"],
        what_could_change=["Demand validation materially underperforms"],
        recommended_next_steps=["Run a paid pilot"],
        upstream_stage_run_ids=stage_ids,
    )

    payload_by_stage = {
        AnalysisStage.MARKET_RESEARCH: market.model_dump(mode="json"),
        AnalysisStage.COMPETITOR_INTELLIGENCE: competitors.model_dump(mode="json"),
        AnalysisStage.CUSTOMER_INTELLIGENCE: customer.model_dump(mode="json"),
        AnalysisStage.BUSINESS_STRATEGY: strategy.model_dump(mode="json"),
        AnalysisStage.FINANCE: finance.model_dump(mode="json"),
        AnalysisStage.DECISION_ANALYTICS: analytics.model_dump(mode="json"),
        AnalysisStage.RISK: risk.model_dump(mode="json"),
        AnalysisStage.INDEPENDENT_VALIDATION: validation.model_dump(mode="json"),
    }

    results = {
        stage: AnalysisResult(
            id=uuid4(),
            analysis_run_id=run_id,
            stage_run_id=stage_ids[stage],
            stage=stage.value,
            result_data=payload,
        )
        for stage, payload in payload_by_stage.items()
    }
    if missing_stage is not None:
        results.pop(missing_stage, None)

    decision_result = AnalysisResult(
        id=uuid4(),
        analysis_run_id=run_id,
        stage_run_id=uuid4(),
        stage=AnalysisStage.INVESTMENT_COMMITTEE.value,
        result_data=decision.model_dump(mode="json"),
    )
    stage_runs = {
        stage_id: SimpleNamespace(
            id=stage_id,
            analysis_run_id=run_id,
            stage=stage.value,
            status=AnalysisStageStatus.COMPLETED.value,
        )
        for stage, stage_id in stage_ids.items()
    }

    db = MagicMock(spec=Session)

    def get_side_effect(model, obj_id):
        if model is Idea and obj_id == idea_id:
            return idea
        if model is AnalysisStageRun:
            return stage_runs.get(obj_id)
        return None

    db.get.side_effect = get_side_effect

    scalar_values = [run, None, decision_result]
    scalar_values.extend(results.get(stage) for stage in DECISION_UPSTREAM_STAGES)
    scalar_values.append(None)  # latest report version
    db.scalar.side_effect = scalar_values
    return db, run_id


def test_generate_structured_report_uses_exact_decision_lineage():
    db, run_id = _mock_db_with_exact_lineage()

    persisted, structured = generate_structured_report(
        db=db, analysis_run_id=run_id
    )

    assert isinstance(structured, StructuredReport)
    assert persisted.analysis_run_id == run_id
    assert structured.decision.decision == VentureDecision.CONDITIONAL_GO
    assert structured.market.market_metrics.tam.status == ReportMetricStatus.UNAVAILABLE
    assert len(structured.sources) == 1

    # Report layer must not invent a month-by-month ramp that Finance never produced.
    assert structured.chart_data.monthly_projections == []
    assert len(structured.chart_data.break_even_comparison) == 3
    assert len(structured.chart_data.risk_matrix) == 1
    db.add.assert_called_once_with(persisted)
    db.flush.assert_called_once()


def test_generate_structured_report_rejects_missing_exact_lineage_result():
    db, run_id = _mock_db_with_exact_lineage(
        missing_stage=AnalysisStage.FINANCE
    )

    with pytest.raises(ReportGenerationError, match="has no persisted result"):
        generate_structured_report(db=db, analysis_run_id=run_id)
