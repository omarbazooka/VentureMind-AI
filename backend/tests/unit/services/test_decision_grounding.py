from uuid import uuid4
import pytest

from app.schemas.analysis import AnalysisProfileSnapshot, AnalysisStage, AnalysisStageStatus
from app.schemas.analytics import DecisionAnalyticsResult, DecisionKPI, DecisionKPIName
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)
from app.schemas.intake import ProfileReadinessStatus
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.risk import RiskAnalysis, RiskLevel
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis, ValidationStatus
from app.services.decision_grounding import (
    DecisionGroundingError,
    validate_grounded_decision,
)


def _unknown_assumption(input_name: FinancialInputName) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        rationale="Unknown test fixture input.",
    )


def _assumptions(scenario: FinancialScenarioKind) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=_unknown_assumption(FinancialInputName.SELLING_PRICE_PER_UNIT),
        sales_volume=_unknown_assumption(FinancialInputName.SALES_VOLUME),
        variable_cost_per_unit=_unknown_assumption(FinancialInputName.VARIABLE_COST_PER_UNIT),
        fixed_costs=_unknown_assumption(FinancialInputName.FIXED_COSTS),
    )


def _finance_result(scenario: FinancialScenarioKind) -> FinancialScenarioResult:
    return FinancialScenarioResult(
        scenario=scenario,
        assumptions=_assumptions(scenario),
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
    )


def _sample_committee_context(validation_status: ValidationStatus = ValidationStatus.PASSED) -> InvestmentCommitteeContext:
    bundle = FinancialScenarioBundle(
        base=_finance_result(FinancialScenarioKind.BASE),
        upside=_finance_result(FinancialScenarioKind.UPSIDE),
        downside=_finance_result(FinancialScenarioKind.DOWNSIDE),
    )
    return InvestmentCommitteeContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={"problem": "Valid"},
        ),
        research_gate=ResearchEvidenceGateResult(
            decision=ResearchGateDecision.ACCEPT,
            can_proceed=True,
            assessments=[
                ResearchStageGateAssessment(
                    stage=stage,
                    attempt=1,
                    stage_status=AnalysisStageStatus.COMPLETED,
                    evidence_quality=ResearchEvidenceQuality.STRONG,
                )
                for stage in [
                    AnalysisStage.MARKET_RESEARCH,
                    AnalysisStage.COMPETITOR_INTELLIGENCE,
                    AnalysisStage.CUSTOMER_INTELLIGENCE,
                ]
            ],
            insufficient_stages=[],
        ),
        business_strategy_stage_run_id=uuid4(),
        business_strategy=BusinessStrategyAnalysis(
            executive_summary="Executive summary"
        ),
        finance_stage_run_id=uuid4(),
        finance_bundle=bundle,
        analytics_stage_run_id=uuid4(),
        decision_analytics=DecisionAnalyticsResult(
            finance_stage_run_id=uuid4(),
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
        ),
        risk_stage_run_id=uuid4(),
        risk_analysis=RiskAnalysis(
            executive_summary="Risk executive summary",
            risks=[],
            limitations=[],
        ),
        validation_stage_run_id=uuid4(),
        validation_analysis=ValidationAnalysis(
            status=validation_status,
            executive_assessment="Audited and verified successfully.",
            issues=[],
            can_proceed=(validation_status != ValidationStatus.FAILED),
        ),
    )


def test_decision_grounding_valid():
    context = _sample_committee_context()
    draft = FinalDecisionDraft(
        decision=VentureDecision.GO,
        confidence=DecisionConfidence.HIGH,
        rationale="All criteria met and validated.",
        supporting_evidence_lineage=["MARKET_RESEARCH", "FINANCE"],
    )
    decision = validate_grounded_decision(draft=draft, context=context)
    assert decision.decision == VentureDecision.GO
    assert decision.confidence == DecisionConfidence.HIGH


def test_decision_grounding_cannot_go_if_validation_failed():
    context = _sample_committee_context(validation_status=ValidationStatus.FAILED)
    draft = FinalDecisionDraft(
        decision=VentureDecision.GO,
        confidence=DecisionConfidence.LOW,
        rationale="Attempting GO despite failed audit.",
    )
    with pytest.raises(DecisionGroundingError, match="cannot issue a decision from a Validation result that blocks progression"):
        validate_grounded_decision(draft=draft, context=context)
