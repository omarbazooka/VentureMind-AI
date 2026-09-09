from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.chat.context import WorkingContext
from app.chat.orchestrator import MissingDatabaseSessionError, TurnOrchestrator
from app.models.report import Report
from app.schemas.turn import ExecutionMode, Intent, SubRequest, TurnUnderstanding


def _mock_context():
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="AI SaaS",
        idea_state="COMPLETED",
        current_user_message="Why was the decision CONDITIONAL_GO?",
        profile_version=1,
        profile_readiness="READY_FOR_ANALYSIS",
        profile_data={"industry": "AI"},
        recent_messages=[],
    )


def _mock_report(idea_id):
    report_data = {
        "id": str(uuid4()),
        "idea_id": str(idea_id),
        "analysis_run_id": str(uuid4()),
        "version": 1,
        "title": "VentureMind Evaluation: AI SaaS",
        "executive_summary": "Promising venture with manageable initial risk.",
        "decision": {
            "decision": "CONDITIONAL_GO",
            "confidence": "MEDIUM",
            "rationale": "High gross margin with manageable pilot sales cycles.",
            "supporting_evidence_lineage": ["FINANCE"],
            "strongest_positive_signals": ["50% margin"],
            "strongest_negative_signals": ["Enterprise sales ramp"],
            "critical_assumptions": ["Fixed costs remain below $4k"],
            "limitations": ["Pilot required"],
            "what_could_change": ["Conversion drops below 2%"],
            "recommended_next_steps": ["Deploy beta"],
        },
        "profile_summary": {},
        "market": {
            "summary": "Large market",
            "evidence_quality": "MODERATE",
            "findings": [],
            "market_metrics": {
                "tam": {"status": "UNAVAILABLE", "explanation": "N/A"},
                "sam": {"status": "UNAVAILABLE", "explanation": "N/A"},
                "som": {"status": "UNAVAILABLE", "explanation": "N/A"},
                "cagr": {"status": "UNAVAILABLE", "explanation": "N/A"},
                "willingness_to_pay": {"status": "UNAVAILABLE", "explanation": "N/A"},
            },
            "limitations": [],
        },
        "competitors": {
            "summary": "Moderate competition",
            "evidence_quality": "MODERATE",
            "competitors": [],
            "findings": [],
            "limitations": [],
        },
        "customer": {
            "summary": "Strong demand",
            "evidence_quality": "MODERATE",
            "findings": [],
            "limitations": [],
        },
        "strategy": {
            "executive_summary": "Direct sales model",
            "positioning": [],
            "value_proposition": [],
            "business_model_implications": [],
            "go_to_market": [],
            "strategic_strengths": [],
            "strategic_weaknesses": [],
            "critical_assumptions": [],
            "limitations": [],
        },
        "finance": {
            "executive_summary": "Base revenue $10,000",
            "base_scenario": {
                "assumptions": {
                    "selling_price_per_unit": {"value": "200.0", "currency": "USD"},
                    "variable_cost_per_unit": {"value": "20.0", "currency": "USD"},
                    "fixed_costs": {"value": "4000.0", "currency": "USD"},
                }
            },
            "upside_scenario": {},
            "downside_scenario": {},
            "comparisons": [],
            "limitations": [],
        },
        "analytics": {
            "kpis": [],
            "scenario_relative_changes": [],
            "sensitivity": None,
            "limitations": [],
        },
        "risk": {
            "executive_summary": "Low tech risk",
            "overall_level": "LOW",
            "risks": [],
            "limitations": [],
        },
        "validation": {
            "status": "PASSED",
            "executive_assessment": "Verified",
            "issues": [],
            "limitations": [],
        },
        "chart_data": {
            "break_even_comparison": [
                {
                    "scenario": "BASE",
                    "break_even_units": 22.2,
                    "break_even_revenue": 4444.0,
                    "currency": "USD",
                }
            ],
            "monthly_projections": [],
            "sensitivity_ranking": [],
            "risk_matrix": [],
        },
        "sources": [],
        "created_at": "2026-09-09T23:00:00Z",
    }
    return Report(
        idea_id=idea_id,
        analysis_run_id=uuid4(),
        version=1,
        report_data=report_data,
    )


def test_orchestrator_handles_ask_report_question():
    orchestrator = TurnOrchestrator()
    context = _mock_context()
    db = MagicMock(spec=Session)
    report = _mock_report(context.idea_id)
    db.scalar.return_value = report

    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req-1",
                intent=Intent.ASK_REPORT_QUESTION,
                confidence=0.9,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    result = orchestrator.execute(turn=turn, context=context, db=db)

    assert "CONDITIONAL_GO" in result.response_text
    assert "VentureMind Report Analysis" in result.response_text


def test_orchestrator_handles_explain_calculation():
    orchestrator = TurnOrchestrator()
    context = _mock_context()
    db = MagicMock(spec=Session)
    report = _mock_report(context.idea_id)
    db.scalar.return_value = report

    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req-2",
                intent=Intent.EXPLAIN_CALCULATION,
                payload={"target_metric": "break_even"},
                confidence=0.95,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    result = orchestrator.execute(turn=turn, context=context, db=db)

    assert "Break-Even Calculation Breakdown" in result.response_text
    assert "22.2 units" in result.response_text


def test_orchestrator_handles_challenge_conclusion():
    orchestrator = TurnOrchestrator()
    context = _mock_context()
    db = MagicMock(spec=Session)
    report = _mock_report(context.idea_id)
    db.scalar.return_value = report

    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req-3",
                intent=Intent.CHALLENGE_CONCLUSION,
                confidence=0.9,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    result = orchestrator.execute(turn=turn, context=context, db=db)

    assert "Critical Stress-Test & Conclusion Challenges" in result.response_text
    assert "Enterprise sales ramp" in result.response_text


def test_orchestrator_fails_without_db_session():
    orchestrator = TurnOrchestrator()
    context = _mock_context()
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req-4",
                intent=Intent.ASK_REPORT_QUESTION,
                confidence=0.9,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    with pytest.raises(MissingDatabaseSessionError):
        orchestrator.execute(turn=turn, context=context, db=None)
