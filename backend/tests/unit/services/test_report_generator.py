from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.idea import Idea
from app.models.report import Report
from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import (
    DecisionAnalyticsResult,
    DecisionKPI,
    DecisionKPIName,
    SensitivityAnalysisResult,
)
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionAnalysis,
    VentureDecision,
)
from app.finance.scenarios import calculate_financial_scenarios
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioInputs,
    FinancialScenarioKind,
    FinancialScenarioResult,
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
from app.schemas.validation import (
    ValidationAnalysis,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStatus,
)
from app.services.report_generator import (
    ReportGenerationError,
    generate_structured_report,
)


def _mock_db_with_stages(missing_stage: str | None = None):
    idea_id = uuid4()
    run_id = uuid4()

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
        status="COMPLETED",
    )

    source = ResearchEvidenceSource(
        source_id="src-1",
        title="Industry Report",
        provenance=EvidenceProvenance.WEB,
        url="https://example.com/data",
    )

    mkt = MarketAnalysis(
        summary="Large growing B2B market",
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Limited regional data"],
    )

    comp = CompetitorAnalysis(
        summary="Fragmented competition",
        competitors=[],
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Private market competitors hidden"],
    )

    cust = CustomerAnalysis(
        summary="High willingness to trial pilot",
        findings=[],
        evidence_sources=[source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Early adopters only"],
    )

    strat = BusinessStrategyAnalysis(
        executive_summary="Direct sales into mid-market SMEs"
    )

    def _assumptions(scen):
        return FinancialAssumptionSet(
            scenario=scen,
            selling_price_per_unit=FinancialAssumption(
                input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
                value=Decimal("200.0"),
                currency="USD",
                unit_label="seat",
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Benchmarked against peers",
            ),
            sales_volume=FinancialAssumption(
                input_name=FinancialInputName.SALES_VOLUME,
                value=Decimal("50.0"),
                unit_label="seat",
                period=FinancialPeriod.MONTHLY,
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Initial sales target",
            ),
            variable_cost_per_unit=FinancialAssumption(
                input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
                value=Decimal("20.0"),
                currency="USD",
                unit_label="seat",
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Compute per seat",
            ),
            fixed_costs=FinancialAssumption(
                input_name=FinancialInputName.FIXED_COSTS,
                value=Decimal("4000.0"),
                currency="USD",
                period=FinancialPeriod.MONTHLY,
                provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
                rationale="Core team and cloud hosting",
            ),
        )

    fin = calculate_financial_scenarios(
        FinancialScenarioInputs(
            base=_assumptions(FinancialScenarioKind.BASE),
            upside=_assumptions(FinancialScenarioKind.UPSIDE),
            downside=_assumptions(FinancialScenarioKind.DOWNSIDE),
        )
    )

    da = DecisionAnalyticsResult(
        finance_stage_run_id=uuid4(),
        kpis=[
            DecisionKPI(
                metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
                scenario=FinancialScenarioKind.BASE,
                value=Decimal("50.0"),
                unit="percent",
                formula="operating_profit / revenue",
                source_financial_metrics=[
                    FinancialMetricName.OPERATING_RESULT,
                    FinancialMetricName.REVENUE,
                ],
                source_financial_inputs=[],
                provenance="CALCULATED",
            )
        ],
    )

    risk = RiskAnalysis(
        executive_summary="Manageable execution and sales cycle risk",
        risks=[
            GroundedRisk(
                category=RiskCategory.FINANCIAL,
                title="Cash burn before breakeven",
                statement="Burn rate may exceed runway if customer acquisition lags.",
                likelihood=RiskLikelihood.MEDIUM,
                impact=RiskImpact.MEDIUM,
                confidence=0.8,
                rationale="Early stage pilot dependencies.",
                risk_score=4,
                risk_level=RiskLevel.MEDIUM,
                mitigation_actions=["Keep fixed overhead variable during beta"],
                supporting_stages=[AnalysisStage.FINANCE],
                financial_metrics=[FinancialMetricName.OPERATING_RESULT],
            )
        ],
        overall_level=RiskLevel.MEDIUM,
        limitations=[],
    )

    val = ValidationAnalysis(
        status=ValidationStatus.PASSED,
        can_proceed=True,
        executive_assessment="Models challenge verified successfully",
        issues=[],
        limitations=[],
        retry_stages=[],
    )

    dec = FinalDecisionAnalysis(
        decision=VentureDecision.CONDITIONAL_GO,
        confidence=DecisionConfidence.MEDIUM,
        rationale="Strong unit margins justify paid pilot phase",
        supporting_evidence_lineage=["FINANCE", "BUSINESS_STRATEGY"],
        strongest_positive_signals=["50% operating margin"],
        strongest_negative_signals=["Sales ramp dependency"],
        critical_assumptions=["Fixed costs stay below $4,000/mo"],
        limitations=["Early stage validation"],
        what_could_change=["Sales conversion drops below 2%"],
        recommended_next_steps=["Deploy prototype with 3 design partners"],
    )

    stage_data = {
        AnalysisStage.MARKET_RESEARCH.value: mkt.model_dump(mode="json"),
        AnalysisStage.COMPETITOR_INTELLIGENCE.value: comp.model_dump(mode="json"),
        AnalysisStage.CUSTOMER_INTELLIGENCE.value: cust.model_dump(mode="json"),
        AnalysisStage.BUSINESS_STRATEGY.value: strat.model_dump(mode="json"),
        AnalysisStage.FINANCE.value: fin.model_dump(mode="json"),
        AnalysisStage.DECISION_ANALYTICS.value: da.model_dump(mode="json"),
        AnalysisStage.RISK.value: risk.model_dump(mode="json"),
        AnalysisStage.INDEPENDENT_VALIDATION.value: val.model_dump(mode="json"),
        AnalysisStage.INVESTMENT_COMMITTEE.value: dec.model_dump(mode="json"),
    }

    if missing_stage:
        stage_data.pop(missing_stage, None)

    results = [
        AnalysisResult(
            id=uuid4(),
            analysis_run_id=run_id,
            stage_run_id=uuid4(),
            stage=stage,
            result_data=data,
        )
        for stage, data in stage_data.items()
    ]

    db = MagicMock(spec=Session)
    db.get.side_effect = lambda model, obj_id: (
        idea if model is Idea and obj_id == idea_id else (
            run if model is AnalysisRun and obj_id == run_id else None
        )
    )

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = results
    db.scalars.return_value = scalars_mock
    db.scalar.return_value = None  # No existing version

    return db, run_id


def test_generate_structured_report_success():
    db, run_id = _mock_db_with_stages()

    persisted, structured = generate_structured_report(
        db=db, analysis_run_id=run_id
    )

    assert isinstance(structured, StructuredReport)
    assert structured.version == 1
    assert structured.decision.decision == VentureDecision.CONDITIONAL_GO
    assert structured.decision.confidence == DecisionConfidence.MEDIUM
    assert structured.market.market_metrics.tam.status == ReportMetricStatus.UNAVAILABLE
    assert structured.market.market_metrics.sam.status == ReportMetricStatus.UNAVAILABLE
    assert len(structured.sources) == 1
    assert structured.sources[0].source_id == "src-1"

    # Check chart data
    assert len(structured.chart_data.break_even_comparison) == 3
    assert len(structured.chart_data.monthly_projections) == 12
    assert len(structured.chart_data.risk_matrix) == 1
    assert structured.chart_data.risk_matrix[0]["score"] == 4

    # DB persistence calls
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_generate_structured_report_fails_when_stage_missing():
    db, run_id = _mock_db_with_stages(
        missing_stage=AnalysisStage.INVESTMENT_COMMITTEE.value
    )

    with pytest.raises(ReportGenerationError, match="missing stage results"):
        generate_structured_report(db=db, analysis_run_id=run_id)
