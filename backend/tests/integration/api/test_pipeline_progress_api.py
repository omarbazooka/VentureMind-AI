from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.analysis_run_input import AnalysisRunInput
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.analysis import (
    AnalysisRunInputStatus,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import FinancialInputName

client = TestClient(app)


def test_progress_not_started():
    with Session(engine) as db:
        idea = Idea(
            title="CleanTech Co",
            raw_initial_idea="Carbon accounting software",
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)
        idea_id = idea.id

    response = client.get(f"/api/v1/ideas/{idea_id}/analysis/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["idea_id"] == str(idea_id)
    assert data["run_status"] == "NOT_STARTED"
    assert data["stage_runs"] == []
    assert data["has_report"] is False


def test_progress_prefers_running_stage_over_later_pending_stage():
    with Session(engine) as db:
        idea = Idea(
            title="FinTech App",
            raw_initial_idea="B2B payments ledger",
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data={"product_name": "LedgerPay"},
            profile_metadata={},
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={"profile_data": {}},
            status=AnalysisRunStatus.RUNNING.value,
        )
        db.add(run)
        db.flush()

        completed_stage = AnalysisStageRun(
            analysis_run_id=run.id,
            stage=AnalysisStage.MARKET_RESEARCH.value,
            attempt=1,
            status=AnalysisStageStatus.COMPLETED.value,
        )
        running_stage = AnalysisStageRun(
            analysis_run_id=run.id,
            stage=AnalysisStage.BUSINESS_STRATEGY.value,
            attempt=1,
            status=AnalysisStageStatus.RUNNING.value,
        )
        later_pending_stage = AnalysisStageRun(
            analysis_run_id=run.id,
            stage=AnalysisStage.FINANCE.value,
            attempt=1,
            status=AnalysisStageStatus.PENDING.value,
        )
        db.add_all(
            [completed_stage, running_stage, later_pending_stage]
        )
        db.commit()

        idea_id = idea.id
        run_id = run.id

    response = client.get(f"/api/v1/ideas/{idea_id}/analysis/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["idea_id"] == str(idea_id)
    assert data["analysis_run_id"] == str(run_id)
    assert data["run_status"] == "RUNNING"
    assert data["current_stage"] == AnalysisStage.BUSINESS_STRATEGY.value
    assert AnalysisStage.MARKET_RESEARCH.value in data["completed_stages"]
    assert len(data["stage_runs"]) == 3


def test_progress_paused_and_answer_flow():
    with Session(engine) as db:
        idea = Idea(
            title="Logistics SaaS",
            raw_initial_idea="Fleet route optimization",
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data={"product_name": "RouteOpt"},
            profile_metadata={},
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={"profile_data": {}},
            status=AnalysisRunStatus.PAUSED_FOR_USER.value,
        )
        db.add(run)
        db.flush()

        finance_stage = AnalysisStageRun(
            analysis_run_id=run.id,
            stage=AnalysisStage.FINANCE.value,
            attempt=1,
            status=AnalysisStageStatus.PAUSED_FOR_USER.value,
        )
        db.add(finance_stage)
        db.flush()

        from app.schemas.finance_runtime import (
            FinanceInputOption,
            FinanceInputOptionBasis,
            FinanceInputRequest,
        )

        finance_request = FinanceInputRequest(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            question="What is the expected price per user per month?",
            options=[
                FinanceInputOption(
                    option_id="tier_standard",
                    input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
                    label="Standard Tier ($49)",
                    value=Decimal("49"),
                    currency="USD",
                    unit_label="seat",
                    period=None,
                    basis=FinanceInputOptionBasis.WEB_EVIDENCE,
                    rationale="Industry benchmark standard pricing",
                    supporting_stages=[AnalysisStage.MARKET_RESEARCH],
                    evidence_source_ids=["src_1"],
                ),
                FinanceInputOption(
                    option_id="tier_enterprise",
                    input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
                    label="Enterprise Tier ($199)",
                    value=Decimal("199"),
                    currency="USD",
                    unit_label="seat",
                    period=None,
                    basis=FinanceInputOptionBasis.WEB_EVIDENCE,
                    rationale="Enterprise pricing benchmark",
                    supporting_stages=[AnalysisStage.MARKET_RESEARCH],
                    evidence_source_ids=["src_2"],
                ),
            ],
            allow_custom=True,
            currency="USD",
            unit_label="seat",
            period=None,
        )

        run_input = AnalysisRunInput(
            analysis_run_id=run.id,
            stage_run_id=finance_stage.id,
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT.value,
            status=AnalysisRunInputStatus.PENDING.value,
            request_data=finance_request.model_dump(mode="json"),
        )
        db.add(run_input)
        db.commit()

        idea_id = idea.id
        input_id = run_input.id

    progress_response = client.get(
        f"/api/v1/ideas/{idea_id}/analysis/progress"
    )
    assert progress_response.status_code == 200
    progress_data = progress_response.json()
    assert progress_data["run_status"] == "PAUSED_FOR_USER"
    assert progress_data["current_stage"] == AnalysisStage.FINANCE.value
    assert progress_data["pending_input"] is not None
    assert (
        progress_data["pending_input"]["input_name"]
        == FinancialInputName.SELLING_PRICE_PER_UNIT.value
    )
    assert len(progress_data["pending_input"]["options"]) == 2

    pending_response = client.get(
        f"/api/v1/ideas/{idea_id}/analysis/inputs/pending"
    )
    assert pending_response.status_code == 200
    pending_data = pending_response.json()
    assert pending_data["input_id"] == str(input_id)
    assert (
        pending_data["question"]
        == "What is the expected price per user per month?"
    )
    assert pending_data["currency"] == "USD"

    # Ambiguous input must not silently prefer one field over the other.
    ambiguous_response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis/inputs/{input_id}/answer",
        json={
            "choice": "tier_standard",
            "value": "49",
        },
    )
    assert ambiguous_response.status_code == 422

    # Parsing a period must be safe, and an invalid period for a selling-price
    # input must be reported as client validation rather than crashing with 500.
    invalid_period_response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis/inputs/{input_id}/answer",
        json={
            "value": "49",
            "currency": "USD",
            "unit_label": "seat",
            "period": "MONTHLY",
        },
    )
    assert invalid_period_response.status_code == 422

    # The server resolves predefined options from the persisted request; an
    # arbitrary client option ID must not be accepted.
    invalid_option_response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis/inputs/{input_id}/answer",
        json={"choice": "not-a-real-option"},
    )
    assert invalid_option_response.status_code == 422

    with patch("app.api.v1.analysis.run_pipeline_sync") as mock_runner:
        answer_response = client.post(
            f"/api/v1/ideas/{idea_id}/analysis/inputs/{input_id}/answer",
            json={"choice": "tier_standard"},
        )
        assert answer_response.status_code == 200
        answer_data = answer_response.json()
        assert answer_data["status"] == "ANSWERED"
        assert answer_data["analysis_run_status"] == "RUNNING"
        mock_runner.assert_called_once()

    with Session(engine) as db:
        updated_input = db.get(AnalysisRunInput, input_id)
        assert updated_input.status == AnalysisRunInputStatus.ANSWERED.value
        updated_run = db.get(AnalysisRun, updated_input.analysis_run_id)
        assert updated_run.status == AnalysisRunStatus.RUNNING.value
