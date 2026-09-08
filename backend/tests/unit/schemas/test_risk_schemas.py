import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import (
    FinancialInputName,
    FinancialMetricName,
)
from app.schemas.risk import (
    GroundedRisk,
    RiskAnalysis,
    RiskCategory,
    RiskDraft,
    RiskImpact,
    RiskLevel,
    RiskLikelihood,
)


def make_financial_risk(**overrides):
    data = {
        "category": RiskCategory.FINANCIAL,
        "title": "Thin downside protection",
        "statement": "Profitability deteriorates materially under weaker assumptions.",
        "likelihood": RiskLikelihood.MEDIUM,
        "impact": RiskImpact.HIGH,
        "confidence": 0.85,
        "rationale": "The downside scenario and sensitivity results show material exposure.",
        "supporting_stages": [
            AnalysisStage.FINANCE,
            AnalysisStage.DECISION_ANALYTICS,
        ],
        "financial_metrics": [FinancialMetricName.OPERATING_RESULT],
        "decision_kpis": [DecisionKPIName.OPERATING_MARGIN_PERCENT],
        "sensitivity_inputs": [FinancialInputName.SELLING_PRICE_PER_UNIT],
    }
    data.update(overrides)
    return data


def test_risk_draft_accepts_explicit_finance_and_analytics_lineage():
    risk = RiskDraft(**make_financial_risk())

    assert AnalysisStage.FINANCE in risk.supporting_stages
    assert (
        FinancialInputName.SELLING_PRICE_PER_UNIT
        in risk.sensitivity_inputs
    )


def test_risk_draft_rejects_no_grounding_lineage():
    data = make_financial_risk(
        supporting_stages=[],
        financial_metrics=[],
        decision_kpis=[],
        sensitivity_inputs=[],
    )

    with pytest.raises(ValidationError):
        RiskDraft(**data)


def test_financial_metric_reference_requires_finance_stage():
    data = make_financial_risk(
        supporting_stages=[AnalysisStage.DECISION_ANALYTICS],
    )

    with pytest.raises(ValidationError):
        RiskDraft(**data)


def test_analytics_reference_requires_decision_analytics_stage():
    data = make_financial_risk(
        supporting_stages=[AnalysisStage.FINANCE],
    )

    with pytest.raises(ValidationError):
        RiskDraft(**data)


def test_grounded_risk_requires_deterministic_score_and_level():
    risk = GroundedRisk(
        **make_financial_risk(),
        risk_score=6,
        risk_level=RiskLevel.HIGH,
    )

    assert risk.risk_score == 6

    with pytest.raises(ValidationError):
        GroundedRisk(
            **make_financial_risk(),
            risk_score=4,
            risk_level=RiskLevel.MEDIUM,
        )


def test_risk_analysis_overall_level_matches_highest_risk():
    high = GroundedRisk(
        **make_financial_risk(),
        risk_score=6,
        risk_level=RiskLevel.HIGH,
    )
    low = GroundedRisk(
        **make_financial_risk(
            title="Limited evidence depth",
            category=RiskCategory.EVIDENCE_QUALITY,
            likelihood=RiskLikelihood.LOW,
            impact=RiskImpact.MEDIUM,
            supporting_stages=[AnalysisStage.MARKET_RESEARCH],
            financial_metrics=[],
            decision_kpis=[],
            sensitivity_inputs=[],
        ),
        risk_score=2,
        risk_level=RiskLevel.LOW,
    )

    analysis = RiskAnalysis(
        executive_summary="Material financial risk remains.",
        risks=[high, low],
        overall_level=RiskLevel.HIGH,
    )

    assert analysis.overall_level == RiskLevel.HIGH

    with pytest.raises(ValidationError):
        RiskAnalysis(
            executive_summary="Invalid aggregate.",
            risks=[high, low],
            overall_level=RiskLevel.LOW,
        )
