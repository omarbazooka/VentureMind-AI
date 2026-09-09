from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.models.report import Report

client = TestClient(app)


def test_get_report_endpoints():
    with Session(engine) as db:
        idea = Idea(
            title="SaaS Platform",
            raw_initial_idea="SaaS workflow automation for clinics",
        )
        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            idea_id=idea.id,
            version=1,
            readiness="READY_FOR_ANALYSIS",
            profile_data={"industry": "HealthTech"},
            profile_metadata={},
            unknown_fields=[],
        )
        db.add(profile)
        db.flush()

        run = AnalysisRun(
            idea_id=idea.id,
            profile_id=profile.id,
            profile_version=1,
            profile_snapshot={"profile_data": {"industry": "HealthTech"}},
            status="COMPLETED",
        )
        db.add(run)
        db.flush()

        mock_report_data = {
            "id": str(uuid4()),
            "idea_id": str(idea.id),
            "analysis_run_id": str(run.id),
            "version": 1,
            "title": f"VentureMind Evaluation: {idea.title}",
            "executive_summary": "Strong unit economics.",
            "decision": {
                "decision": "GO",
                "confidence": "HIGH",
                "rationale": "High margin opportunity.",
                "supporting_evidence_lineage": ["FINANCE"],
                "strongest_positive_signals": ["High LTV"],
                "strongest_negative_signals": [],
                "critical_assumptions": [],
                "limitations": [],
                "what_could_change": [],
                "recommended_next_steps": ["Build MVP"],
            },
            "profile_summary": {"industry": "HealthTech"},
            "market": {
                "summary": "Large addressable market",
                "evidence_quality": "MODERATE",
                "findings": [],
                "market_metrics": {
                    "tam": {
                        "status": "UNAVAILABLE",
                        "explanation": "Evidence does not support TAM calculation",
                    },
                    "sam": {
                        "status": "UNAVAILABLE",
                        "explanation": "Evidence does not support SAM calculation",
                    },
                    "som": {
                        "status": "UNAVAILABLE",
                        "explanation": "Evidence does not support SOM calculation",
                    },
                    "cagr": {
                        "status": "UNAVAILABLE",
                        "explanation": "Evidence does not support CAGR calculation",
                    },
                    "willingness_to_pay": {
                        "status": "UNAVAILABLE",
                        "explanation": "Evidence does not support willingness-to-pay estimation",
                    },
                },
                "limitations": [],
            },
            "competitors": {
                "summary": "Low competition",
                "evidence_quality": "MODERATE",
                "competitors": [],
                "findings": [],
                "limitations": [],
            },
            "customer": {
                "summary": "Strong customer demand",
                "evidence_quality": "MODERATE",
                "findings": [],
                "limitations": [],
            },
            "strategy": {
                "executive_summary": "Direct outreach to private clinics",
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
                "executive_summary": "Profitable at month 4",
                "base_scenario": {},
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
                "executive_summary": "Low regulatory hurdle",
                "overall_level": "LOW",
                "risks": [],
                "limitations": [],
            },
            "validation": {
                "status": "PASSED",
                "executive_assessment": "All model checks passed",
                "issues": [],
                "limitations": [],
            },
            "chart_data": {
                "break_even_comparison": [],
                "monthly_projections": [],
                "sensitivity_ranking": [],
                "risk_matrix": [],
            },
            "sources": [],
            "created_at": "2026-09-09T23:00:00Z",
        }

        report = Report(
            idea_id=idea.id,
            analysis_run_id=run.id,
            version=1,
            report_data=mock_report_data,
        )
        db.add(report)
        db.commit()

        idea_id_str = str(idea.id)

    # 1. Latest report
    res = client.get(f"/api/v1/ideas/{idea_id_str}/report/latest")
    assert res.status_code == 200
    data = res.json()
    assert data["version"] == 1
    assert data["decision"]["decision"] == "GO"
    assert data["market"]["market_metrics"]["tam"]["status"] == "UNAVAILABLE"

    # 2. List reports
    res_list = client.get(f"/api/v1/ideas/{idea_id_str}/reports")
    assert res_list.status_code == 200
    versions = res_list.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1

    # 3. Get version 1
    res_v1 = client.get(f"/api/v1/ideas/{idea_id_str}/reports/1")
    assert res_v1.status_code == 200
    assert res_v1.json()["version"] == 1

    # 4. Get non-existent version
    res_v999 = client.get(f"/api/v1/ideas/{idea_id_str}/reports/999")
    assert res_v999.status_code == 404

    # 5. Non-existent idea
    res_fake = client.get(f"/api/v1/ideas/{uuid4()}/report/latest")
    assert res_fake.status_code == 404

    # 6. Execute report action: EXPLAIN_CALCULATION
    act_res = client.post(
        f"/api/v1/ideas/{idea_id_str}/report/action",
        json={"action": "EXPLAIN_CALCULATION", "target_metric": "break_even"},
    )
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["action"] == "EXPLAIN_CALCULATION"
    assert "Break-Even Calculation" in act_data["title"]

    # 7. Execute report action: CHALLENGE_CONCLUSION
    chal_res = client.post(
        f"/api/v1/ideas/{idea_id_str}/report/action",
        json={"action": "CHALLENGE_CONCLUSION"},
    )
    assert chal_res.status_code == 200
    assert "Adversarial Conclusion Challenge" in chal_res.json()["title"]

    # 8. Execute report action: ASK_VENTUREMIND
    ask_res = client.post(
        f"/api/v1/ideas/{idea_id_str}/report/action",
        json={"action": "ASK_VENTUREMIND", "question": "Is this venture viable?"},
    )
    assert ask_res.status_code == 200
    assert "Grounded Q&A Response" in ask_res.json()["title"]
