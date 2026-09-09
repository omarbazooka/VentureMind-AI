from uuid import uuid4
import pytest

from app.schemas.analysis import AnalysisProfileSnapshot, AnalysisStage, AnalysisStageStatus
from app.schemas.analytics import DecisionAnalyticsResult, DecisionKPI, DecisionKPIName
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
from app.schemas.validation_runtime import ValidationAnalysisContext
from app.services.validation_grounding import (
    ValidationGroundingError,
    validate_grounded_validation_analysis,
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


def _sample_context() -> ValidationAnalysisContext:
    src = ResearchEvidenceSource(
        source_id="src-valid-1",
        title="Valid Source",
        provenance=EvidenceProvenance.WEB,
        url="https://example.com/source",
    )
    market = MarketAnalysis(
        summary="Market summary",
        findings=[],
        evidence_sources=[src],
        evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
        limitations=["Market evidence is limited."],
    )
    research_gate = ResearchEvidenceGateResult(
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
    )
    bundle = FinancialScenarioBundle(
        base=_finance_result(FinancialScenarioKind.BASE),
        upside=_finance_result(FinancialScenarioKind.UPSIDE),
        downside=_finance_result(FinancialScenarioKind.DOWNSIDE),
    )
    analytics = DecisionAnalyticsResult(
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
    )
    risk = RiskAnalysis(
        executive_summary="Risk summary",
        risks=[],
        limitations=[],
    )
    strategy = BusinessStrategyAnalysis(
        executive_summary="Solid strategic positioning"
    )

    return ValidationAnalysisContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={"problem": "Existing problem"},
        ),
        research_gate=research_gate,
        market_analysis=market,
        business_strategy_stage_run_id=uuid4(),
        business_strategy=strategy,
        finance_stage_run_id=uuid4(),
        finance_bundle=bundle,
        analytics_stage_run_id=uuid4(),
        decision_analytics=analytics,
        risk_stage_run_id=uuid4(),
        risk_analysis=risk,
    )


def test_validation_grounding_success():
    context = _sample_context()
    draft = ValidationDraft(
        executive_assessment="Thoroughly grounded and solid analysis.",
        issues=[
            ValidationIssue(
                category=ValidationIssueCategory.UNREFLECTED_RISK,
                severity=ValidationSeverity.LOW,
                description="Minor risk noted in Strategy not fully highlighted in Risk.",
                affected_stages=[AnalysisStage.RISK],
                evidence_ids=["src-valid-1"],
            )
        ],
    )
    result = validate_grounded_validation_analysis(draft=draft, context=context)
    assert result.status == ValidationStatus.PASSED_WITH_WARNINGS
    assert result.can_proceed is True
    assert len(result.issues) == 1


def test_validation_grounding_rejects_hallucinated_evidence():
    context = _sample_context()
    draft = ValidationDraft(
        executive_assessment="Issue with evidence.",
        issues=[
            ValidationIssue(
                category=ValidationIssueCategory.UNSUPPORTED_CLAIM,
                severity=ValidationSeverity.MEDIUM,
                description="Fake citation cited.",
                affected_stages=[AnalysisStage.MARKET_RESEARCH],
                evidence_ids=["src-fake-999"],
            )
        ],
    )
    with pytest.raises(ValidationGroundingError, match="non-existent evidence ID"):
        validate_grounded_validation_analysis(draft=draft, context=context)


def test_validation_grounding_critical_blocks_progression():
    context = _sample_context()
    draft = ValidationDraft(
        executive_assessment="Critical mismatch found.",
        issues=[
            ValidationIssue(
                category=ValidationIssueCategory.CONTRADICTORY_CLAIM,
                severity=ValidationSeverity.CRITICAL,
                description="Critical contradiction between TAM and target customer definition.",
                affected_stages=[AnalysisStage.MARKET_RESEARCH],
                evidence_ids=["src-valid-1"],
            )
        ],
    )
    result = validate_grounded_validation_analysis(draft=draft, context=context)
    assert result.status == ValidationStatus.FAILED
    assert result.can_proceed is False
