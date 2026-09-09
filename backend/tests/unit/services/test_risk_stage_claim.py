from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
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
from app.schemas.risk_runtime import RiskAnalysisContext
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.risk_stage import (
    RiskStageDependencyError,
    RiskStageStateError,
    claim_risk_stage,
)


def _unknown_assumption(
    input_name: FinancialInputName,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        rationale="Unknown test fixture input.",
    )


def _dummy_result(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioResult:
    assumptions = FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=_unknown_assumption(
            FinancialInputName.SELLING_PRICE_PER_UNIT
        ),
        sales_volume=_unknown_assumption(
            FinancialInputName.SALES_VOLUME
        ),
        variable_cost_per_unit=_unknown_assumption(
            FinancialInputName.VARIABLE_COST_PER_UNIT
        ),
        fixed_costs=_unknown_assumption(
            FinancialInputName.FIXED_COSTS
        ),
    )
    return FinancialScenarioResult(
        scenario=scenario,
        assumptions=assumptions,
    )


def _dummy_bundle() -> FinancialScenarioBundle:
    return FinancialScenarioBundle(
        base=_dummy_result(FinancialScenarioKind.BASE),
        upside=_dummy_result(FinancialScenarioKind.UPSIDE),
        downside=_dummy_result(FinancialScenarioKind.DOWNSIDE),
    )


def _insufficient_research_gate() -> ResearchEvidenceGateResult:
    stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    return ResearchEvidenceGateResult(
        decision=ResearchGateDecision.INSUFFICIENT,
        can_proceed=True,
        assessments=[
            ResearchStageGateAssessment(
                stage=stage,
                attempt=1,
                stage_status=AnalysisStageStatus.COMPLETED,
                evidence_quality=ResearchEvidenceQuality.INSUFFICIENT,
            )
            for stage in stages
        ],
        insufficient_stages=stages,
    )


def _valid_context() -> RiskAnalysisContext:
    finance_stage_run_id = uuid4()
    return RiskAnalysisContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=ProfileReadinessStatus.READY_FOR_ANALYSIS,
            profile_data={"idea_description": "Gym SaaS"},
        ),
        research_gate=_insufficient_research_gate(),
        business_strategy_stage_run_id=uuid4(),
        business_strategy=BusinessStrategyAnalysis(
            executive_summary="Proceed cautiously."
        ),
        finance_stage_run_id=finance_stage_run_id,
        finance_bundle=_dummy_bundle(),
        analytics_stage_run_id=uuid4(),
        decision_analytics=DecisionAnalyticsResult(
            finance_stage_run_id=finance_stage_run_id
        ),
    )


def make_setup():
    analysis_run_id = uuid4()
    stage_run = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.RISK.value,
        attempt=1,
        status=AnalysisStageStatus.PENDING.value,
        started_at=None,
        error_code=None,
        error_message=None,
    )
    analysis_run = SimpleNamespace(
        id=analysis_run_id,
        status=AnalysisRunStatus.RUNNING.value,
    )
    db = Mock()
    db.scalar.return_value = stage_run
    db.get.return_value = analysis_run
    return db, stage_run, analysis_run


def test_claim_risk_stage_builds_context_before_running():
    db, stage_run, analysis_run = make_setup()
    context = _valid_context()

    with patch(
        "app.services.risk_stage._build_context",
        return_value=context,
    ):
        claim = claim_risk_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert claim.stage == AnalysisStage.RISK
    assert claim.analysis_run_id == analysis_run.id
    assert claim.context is context
    assert stage_run.status == AnalysisStageStatus.RUNNING.value
    assert stage_run.started_at is not None
    db.flush.assert_called_once()


def test_claim_risk_stage_requires_pending_state():
    db, stage_run, _ = make_setup()
    stage_run.status = AnalysisStageStatus.RUNNING.value

    with pytest.raises(RiskStageStateError):
        claim_risk_stage(
            db=db,
            stage_run_id=stage_run.id,
        )


def test_claim_risk_stage_keeps_pending_when_context_is_missing():
    db, stage_run, _ = make_setup()

    with patch(
        "app.services.risk_stage._build_context",
        side_effect=RiskStageDependencyError(
            "missing upstream context"
        ),
    ):
        with pytest.raises(RiskStageDependencyError):
            claim_risk_stage(
                db=db,
                stage_run_id=stage_run.id,
            )

    assert stage_run.status == AnalysisStageStatus.PENDING.value
