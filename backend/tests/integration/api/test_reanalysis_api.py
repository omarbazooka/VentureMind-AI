from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.models.report import Report
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)

client = TestClient(app)


def test_reanalysis_creates_new_run_and_preserves_history(monkeypatch):
    monkeypatch.setattr("app.api.v1.analysis.run_pipeline_sync", lambda *args, **kwargs: None)
    with Session(engine) as db:
        idea = Idea(
            title="Reanalysis Test Idea",
            raw_initial_idea="SaaS for pet clinics",
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data={
                "idea_description": "Clinic management SaaS.",
                "target_customers": ["Vets"],
                "target_country": "US",
                "idea_pricing": "49.00",
            },
            profile_metadata={
                "idea_description": {"provenance": "USER"},
                "target_customers": {"provenance": "USER"},
                "target_country": {"provenance": "USER"},
                "idea_pricing": {"provenance": "USER"},
            },
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run1 = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={
                "readiness": "READY_FOR_ANALYSIS",
                "profile_data": profile.profile_data,
                "profile_metadata": profile.profile_metadata,
                "unknown_fields": [],
            },
            status=AnalysisRunStatus.COMPLETED.value,
        )
        db.add(run1)
        db.flush()

        # Add stage runs and results for run1
        for stage in (
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.COMPETITOR_INTELLIGENCE,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
            AnalysisStage.BUSINESS_STRATEGY,
            AnalysisStage.FINANCE,
            AnalysisStage.DECISION_ANALYTICS,
            AnalysisStage.RISK,
            AnalysisStage.INDEPENDENT_VALIDATION,
            AnalysisStage.INVESTMENT_COMMITTEE,
        ):
            sr = AnalysisStageRun(
                analysis_run_id=run1.id,
                stage=stage.value,
                attempt=1,
                status=AnalysisStageStatus.COMPLETED.value,
            )
            db.add(sr)
            db.flush()

            ar = AnalysisResult(
                analysis_run_id=run1.id,
                stage_run_id=sr.id,
                stage=stage.value,
                result_data={"summary": f"Result for {stage.value}"},
            )
            db.add(ar)

        db.commit()
        idea_id = idea.id
        run1_id = run1.id

    # Call reanalysis endpoint
    response = client.post(
        f"/api/v1/ideas/{idea_id}/reanalyze",
        json={
            "target_stage": "FINANCE",
            "profile_updates": {"idea_pricing": "99.00"},
            "reason": "Test higher pricing tier",
        },
    )
    assert response.status_code == 202
    data = response.json()

    assert data["idea_id"] == str(idea_id)
    assert data["new_analysis_run_id"] != str(run1_id)
    assert data["new_profile_version"] == 2
    assert "FINANCE" in data["invalidated_stages"]
    assert "INVESTMENT_COMMITTEE" in data["invalidated_stages"]
    assert "MARKET_RESEARCH" in data["reused_stages"]
    assert "BUSINESS_STRATEGY" in data["reused_stages"]
    assert len(data["reused_result_ids"]) > 0

    # Verify in DB that old run and its stage runs were preserved without cloning
    with Session(engine) as db:
        old_stage_runs = list(
            db.scalars(
                select(AnalysisStageRun)
                .where(AnalysisStageRun.analysis_run_id == run1_id)
            ).all()
        )
        assert len(old_stage_runs) == 9

        # Verify new profile version 2 exists
        p2 = db.scalar(
            select(IdeaProfile)
            .where(IdeaProfile.idea_id == idea_id, IdeaProfile.version == 2)
        )
        assert p2 is not None
        assert p2.profile_data["idea_pricing"] == "99.00"


def test_report_comparison_generates_diffs():
    with Session(engine) as db:
        idea = Idea(
            title="Comparison Test Idea",
            raw_initial_idea="SaaS for gyms",
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data={"idea_description": "Gym SaaS"},
            profile_metadata={},
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run1 = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={"readiness": "READY_FOR_ANALYSIS"},
            status=AnalysisRunStatus.COMPLETED.value,
        )
        db.add(run1)
        db.flush()

        run2 = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=2,
            profile_snapshot={
                "readiness": "READY_FOR_ANALYSIS",
                "lineage": {
                    "source_run_id": str(run1.id),
                    "reused_stages": ["MARKET_RESEARCH"],
                    "invalidated_stages": ["FINANCE"],
                    "reanalysis_reason": "Price bump",
                },
            },
            status=AnalysisRunStatus.COMPLETED.value,
        )
        db.add(run2)
        db.flush()

        rep1 = Report(
            idea_id=idea.id,
            analysis_run_id=run1.id,
            version=1,
            report_data={
                "executive_summary": "v1 summary",
                "investment_committee": {
                    "decision": "CAUTION",
                    "confidence": "MEDIUM",
                },
                "financial_analysis": {
                    "key_metrics": {
                        "net_present_value": {"value": "-10000.00"},
                        "internal_rate_of_return": {"value": "0.05"},
                        "payback_period_months": {"value": "36"},
                    }
                },
                "risk_assessment": {
                    "identified_risks": [
                        {"title": "Pricing resistance", "impact": "HIGH"},
                        {"title": "Churn risk", "impact": "HIGH"},
                    ]
                },
            },
        )
        db.add(rep1)

        rep2 = Report(
            idea_id=idea.id,
            analysis_run_id=run2.id,
            version=2,
            report_data={
                "executive_summary": "v2 summary",
                "investment_committee": {
                    "decision": "GO",
                    "confidence": "HIGH",
                },
                "financial_analysis": {
                    "key_metrics": {
                        "net_present_value": {"value": "150000.00"},
                        "internal_rate_of_return": {"value": "0.32"},
                        "payback_period_months": {"value": "14"},
                    }
                },
                "risk_assessment": {
                    "identified_risks": [
                        {"title": "Market size", "impact": "MEDIUM"},
                    ]
                },
            },
        )
        db.add(rep2)
        db.commit()
        idea_id = idea.id

    response = client.get(f"/api/v1/ideas/{idea_id}/report/compare?v1=1&v2=2")
    assert response.status_code == 200
    data = response.json()

    assert data["idea_id"] == str(idea_id)
    assert data["v1_version"] == 1
    assert data["v2_version"] == 2

    # Check decision comparison
    assert data["decision_comparison"]["v1_decision"] == "CAUTION"
    assert data["decision_comparison"]["v2_decision"] == "GO"
    assert data["decision_comparison"]["changed"] is True

    # Check financial metrics diff
    metrics_by_name = {m["metric_name"]: m for m in data["financial_comparison"]}
    npv = metrics_by_name["net_present_value"]
    assert npv["v1_value"] == "-10000.00"
    assert npv["v2_value"] == "150000.00"
    assert npv["delta"] == 160000.0
    assert npv["direction"] == "UP"

    # Check risk comparison
    assert data["risk_comparison"]["v1_high_risks"] == 2
    assert data["risk_comparison"]["v2_high_risks"] == 0
    assert data["risk_comparison"]["net_risk_change"] == -1

    # Check lineage
    assert data["lineage_comparison"]["reused_stages"] == ["MARKET_RESEARCH"]
    assert data["lineage_comparison"]["reason"] == "Price bump"
    assert len(data["executive_takeaway"]) > 10
