from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.analytics import (
    DecisionAnalyticsResult,
    DecisionKPI,
    DecisionKPIName,
    InputSensitivityResult,
    SensitivityAnalysisResult,
)
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import (
    EvidenceProvenance,
    MarketAnalysis,
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
)
from app.schemas.risk import (
    RiskCategory,
    RiskDraft,
    RiskDraftAnalysis,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)
from app.schemas.risk_runtime import RiskAnalysisContext
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.risk_grounding import (
    RiskGroundingError,
    finalize_risk_analysis,
)


def _finance_result(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioResult:
    return FinancialScenarioResult.model_construct(
        scenario=scenario,
        assumptions=None,
        metrics=[
            CalculatedFinancialMetric(
                metric_name=FinancialMetricName.OPERATING_RESULT,
                value=100,
                currency="EGP",
                unit="money",
                formula="test formula",
                input_names=[FinancialInputName.FIXED_COSTS],
                period=FinancialPeriod.MONTHLY,
            )
        ],
        missing_critical_inputs=[],
        limitations=[],
    )


def make_context() -> RiskAnalysisContext:
    finance_stage_run_id = uuid4()
    market_source = ResearchEvidenceSource(
        source_id="market-source-1",
        provenance=EvidenceProvenance.WEB,
        title="Market source",
        url="https://example.com/market",
    )
    market = MarketAnalysis(
        summary="Limited market evidence.",
        findings=[],
        evidence_sources=[market_source],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Market evidence is limited."],
    )
    research_stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    gate = ResearchEvidenceGateResult.model_construct(
        can_proceed=True,
        insufficient_stages=research_stages,
    )
    bundle = FinancialScenarioBundle.model_construct(
        base=_finance_result(FinancialScenarioKind.BASE),
        upside=_finance_result(FinancialScenarioKind.UPSIDE),
        downside=_finance_result(FinancialScenarioKind.DOWNSIDE),
        comparisons=[],
        limitations=[],
    )
    sensitivity_item = InputSensitivityResult.model_construct(
        input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
        decrease=None,
        increase=None,
        max_abs_ranking_metric_change_percent=25,
        rank=1,
    )
    sensitivity = SensitivityAnalysisResult.model_construct(
        shock_percent=10,
        ranking_metric=FinancialMetricName.OPERATING_RESULT,
        inputs=[sensitivity_item],
        limitations=[],
    )
    analytics = DecisionAnalyticsResult(
        finance_stage_run_id=finance_stage_run_id,
        kpis=[
            DecisionKPI(
                metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
                scenario=FinancialScenarioKind.BASE,
                value=20,
                formula="operating_result / revenue * 100",
                source_financial_metrics=[
                    FinancialMetricName.REVENUE,
                    FinancialMetricName.OPERATING_RESULT,
                ],
            )
        ],
        sensitivity=sensitivity,
    )

    return RiskAnalysisContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={
                "idea_description": "Gym management SaaS",
                "target_country": "Egypt",
            },
        ),
        research_gate=gate,
        market_analysis=market,
        business_strategy_stage_run_id=uuid4(),
        business_strategy=BusinessStrategyAnalysis(
            executive_summary="Proceed cautiously."
        ),
        finance_stage_run_id=finance_stage_run_id,
        finance_bundle=bundle,
        analytics_stage_run_id=uuid4(),
        decision_analytics=analytics,
    )


def make_risk(**overrides) -> RiskDraft:
    data = {
        "category": RiskCategory.FINANCIAL,
        "title": "Profit sensitivity",
        "statement": "Profitability is sensitive to pricing assumptions.",
        "likelihood": RiskLikelihood.MEDIUM,
        "impact": RiskImpact.HIGH,
        "confidence": 0.8,
        "rationale": "Finance and sensitivity outputs show material exposure.",
        "supporting_stages": [
            AnalysisStage.FINANCE,
            AnalysisStage.DECISION_ANALYTICS,
        ],
        "financial_metrics": [FinancialMetricName.OPERATING_RESULT],
        "decision_kpis": [DecisionKPIName.OPERATING_MARGIN_PERCENT],
        "sensitivity_inputs": [FinancialInputName.SELLING_PRICE_PER_UNIT],
    }
    data.update(overrides)
    return RiskDraft(**data)


def test_finalizes_risk_score_level_order_and_gate_limitations():
    context = make_context()
    low = make_risk(
        title="Smaller execution concern",
        category=RiskCategory.EXECUTION,
        likelihood=RiskLikelihood.LOW,
        impact=RiskImpact.MEDIUM,
    )
    high = make_risk()

    result = finalize_risk_analysis(
        draft=RiskDraftAnalysis(
            executive_summary="Financial exposure is the primary risk.",
            risks=[low, high],
        ),
        context=context,
    )

    assert result.risks[0].title == "Profit sensitivity"
    assert result.risks[0].risk_score == 6
    assert result.risks[0].risk_level == RiskLevel.HIGH
    assert result.risks[1].risk_score == 2
    assert result.overall_level == RiskLevel.HIGH
    assert any(
        "MARKET_RESEARCH as INSUFFICIENT_EVIDENCE" in limitation
        for limitation in result.limitations
    )


def test_rejects_unknown_profile_field():
    context = make_context()
    risk = make_risk(
        profile_fields=["invented_field"],
    )

    with pytest.raises(RiskGroundingError):
        finalize_risk_analysis(
            draft=RiskDraftAnalysis(
                executive_summary="Invalid lineage.",
                risks=[risk],
            ),
            context=context,
        )


def test_evidence_source_must_belong_to_declared_research_stage():
    context = make_context()
    risk = make_risk(
        supporting_stages=[AnalysisStage.CUSTOMER_INTELLIGENCE],
        financial_metrics=[],
        decision_kpis=[],
        sensitivity_inputs=[],
        evidence_source_ids=["market-source-1"],
    )

    with pytest.raises(RiskGroundingError):
        finalize_risk_analysis(
            draft=RiskDraftAnalysis(
                executive_summary="Invalid evidence lineage.",
                risks=[risk],
            ),
            context=context,
        )


def test_rejects_finance_metric_not_present_in_context():
    context = make_context()
    risk = make_risk(
        financial_metrics=[FinancialMetricName.RUNWAY_PERIODS],
    )

    with pytest.raises(RiskGroundingError):
        finalize_risk_analysis(
            draft=RiskDraftAnalysis(
                executive_summary="Invalid Finance lineage.",
                risks=[risk],
            ),
            context=context,
        )


def test_stage_only_evidence_quality_accepts_insufficient_research_stage():
    context = make_context()
    risk = RiskDraft(
        category=RiskCategory.EVIDENCE_QUALITY,
        title="Insufficient market evidence",
        statement="Market evidence is insufficient for a strong conclusion.",
        likelihood=RiskLikelihood.MEDIUM,
        impact=RiskImpact.MEDIUM,
        confidence=0.5,
        rationale="The Research Evidence Gate marked market research insufficient.",
        supporting_stages=[AnalysisStage.MARKET_RESEARCH],
    )

    result = finalize_risk_analysis(
        draft=RiskDraftAnalysis(
            executive_summary="Evidence quality remains a decision risk.",
            risks=[risk],
        ),
        context=context,
    )

    assert result.risks[0].category == RiskCategory.EVIDENCE_QUALITY


def test_stage_only_evidence_quality_rejects_stage_not_marked_insufficient():
    context = make_context()
    accepted_market_gate = context.research_gate.model_copy(
        update={
            "insufficient_stages": [
                AnalysisStage.COMPETITOR_INTELLIGENCE,
                AnalysisStage.CUSTOMER_INTELLIGENCE,
            ]
        }
    )
    context = context.model_copy(
        update={"research_gate": accepted_market_gate}
    )
    risk = RiskDraft(
        category=RiskCategory.EVIDENCE_QUALITY,
        title="Invented market evidence weakness",
        statement="Market evidence is insufficient.",
        likelihood=RiskLikelihood.MEDIUM,
        impact=RiskImpact.MEDIUM,
        confidence=0.5,
        rationale="This should be rejected because the gate did not mark it insufficient.",
        supporting_stages=[AnalysisStage.MARKET_RESEARCH],
    )

    with pytest.raises(RiskGroundingError):
        finalize_risk_analysis(
            draft=RiskDraftAnalysis(
                executive_summary="Invalid gate lineage.",
                risks=[risk],
            ),
            context=context,
        )
