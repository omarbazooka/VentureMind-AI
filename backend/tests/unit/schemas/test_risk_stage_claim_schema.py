from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisStage
from app.schemas.risk_runtime import RiskStageClaim


def test_risk_stage_claim_requires_risk_stage():
    with pytest.raises(ValidationError):
        RiskStageClaim.model_validate(
            {
                "stage_run_id": uuid4(),
                "analysis_run_id": uuid4(),
                "stage": AnalysisStage.FINANCE,
                "attempt": 1,
                "context": {},
            }
        )
