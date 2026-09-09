from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisStage
from app.schemas.analytics_runtime import AnalyticsStageClaim
from app.schemas.finance import (
    FinancialAssumptionSet,
    FinancialScenarioBundle,
    FinancialScenarioKind,
    FinancialScenarioResult,
)


def _dummy_result(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioResult:
    assumptions = FinancialAssumptionSet.model_construct(
        scenario=scenario,
    )
    return FinancialScenarioResult.model_construct(
        scenario=scenario,
        assumptions=assumptions,
        metrics=[],
        missing_critical_inputs=[],
        limitations=[],
    )


def dummy_bundle() -> FinancialScenarioBundle:
    return FinancialScenarioBundle.model_construct(
        base=_dummy_result(FinancialScenarioKind.BASE),
        upside=_dummy_result(FinancialScenarioKind.UPSIDE),
        downside=_dummy_result(FinancialScenarioKind.DOWNSIDE),
        comparisons=[],
        limitations=[],
    )


def test_analytics_stage_claim_requires_decision_analytics_stage():
    with pytest.raises(ValidationError):
        AnalyticsStageClaim(
            stage_run_id=uuid4(),
            analysis_run_id=uuid4(),
            stage=AnalysisStage.FINANCE,
            attempt=1,
            finance_stage_run_id=uuid4(),
            finance_bundle=dummy_bundle(),
        )
