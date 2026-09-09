from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.chat.analysis_context import (
    ChatAnalysisContextError,
    load_chat_analysis_context,
)
from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.risk import RiskAnalysis


def _result(data):
    return SimpleNamespace(result_data=data)


def test_loads_only_requested_decision_analytics_context():
    db = Mock(spec=Session)
    idea_id = uuid4()
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=idea_id,
    )
    analytics = DecisionAnalyticsResult(
        finance_stage_run_id=uuid4(),
    )
    db.scalar.return_value = _result(
        analytics.model_dump(mode="json")
    )

    context = load_chat_analysis_context(
        db=db,
        idea_id=idea_id,
        analysis_run_id=run_id,
        stages={AnalysisStage.DECISION_ANALYTICS},
    )

    assert context.decision_analytics is not None
    assert context.risk_analysis is None
    assert db.scalar.call_count == 1


def test_loads_validated_analytics_and_risk_results():
    db = Mock(spec=Session)
    idea_id = uuid4()
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=idea_id,
    )
    analytics = DecisionAnalyticsResult(
        finance_stage_run_id=uuid4(),
    )
    risk = RiskAnalysis(
        executive_summary="No material grounded risks were identified.",
        risks=[],
        overall_level=None,
    )
    db.scalar.side_effect = [
        _result(analytics.model_dump(mode="json")),
        _result(risk.model_dump(mode="json")),
    ]

    context = load_chat_analysis_context(
        db=db,
        idea_id=idea_id,
        analysis_run_id=run_id,
    )

    assert context.decision_analytics == analytics
    assert context.risk_analysis == risk


def test_missing_completed_result_is_returned_as_unavailable():
    db = Mock(spec=Session)
    idea_id = uuid4()
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=idea_id,
    )
    db.scalar.return_value = None

    context = load_chat_analysis_context(
        db=db,
        idea_id=idea_id,
        analysis_run_id=run_id,
        stages={AnalysisStage.RISK},
    )

    assert context.risk_analysis is None


def test_rejects_cross_idea_analysis_run_access():
    db = Mock(spec=Session)
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=uuid4(),
    )

    with pytest.raises(ChatAnalysisContextError):
        load_chat_analysis_context(
            db=db,
            idea_id=uuid4(),
            analysis_run_id=run_id,
        )

    db.scalar.assert_not_called()


def test_rejects_invalid_persisted_structured_result():
    db = Mock(spec=Session)
    idea_id = uuid4()
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=idea_id,
    )
    db.scalar.return_value = _result(
        {"invalid": "analytics payload"}
    )

    with pytest.raises(ChatAnalysisContextError):
        load_chat_analysis_context(
            db=db,
            idea_id=idea_id,
            analysis_run_id=run_id,
            stages={AnalysisStage.DECISION_ANALYTICS},
        )


def test_rejects_non_day8_analysis_stage_request():
    db = Mock(spec=Session)

    with pytest.raises(ValueError):
        load_chat_analysis_context(
            db=db,
            idea_id=uuid4(),
            analysis_run_id=uuid4(),
            stages={AnalysisStage.FINANCE},
        )

    db.get.assert_not_called()


def test_loads_validation_and_decision_stages():
    db = Mock(spec=Session)
    idea_id = uuid4()
    run_id = uuid4()
    db.get.return_value = SimpleNamespace(
        id=run_id,
        idea_id=idea_id,
    )
    val_data = {
        "status": "PASSED",
        "can_proceed": True,
        "executive_assessment": "Assumptions challenged and verified.",
        "issues": [],
        "limitations": [],
        "retry_stages": [],
    }
    dec_data = {
        "decision": "CONDITIONAL_GO",
        "confidence": "HIGH",
        "rationale": "High margin opportunity.",
        "supporting_evidence_lineage": ["FINANCE"],
        "strongest_positive_signals": ["High LTV"],
        "strongest_negative_signals": [],
        "critical_assumptions": [],
        "limitations": [],
        "what_could_change": [],
        "recommended_next_steps": ["Run pilot"],
    }
    db.scalar.side_effect = [
        _result(val_data),
        _result(dec_data),
    ]

    context = load_chat_analysis_context(
        db=db,
        idea_id=idea_id,
        analysis_run_id=run_id,
        stages={
            AnalysisStage.INDEPENDENT_VALIDATION,
            AnalysisStage.INVESTMENT_COMMITTEE,
        },
    )

    assert context.validation_analysis is not None
    assert context.validation_analysis.status.value == "PASSED"
    assert context.final_decision is not None
    assert context.final_decision.decision.value == "CONDITIONAL_GO"

