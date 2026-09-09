import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisStage
from app.schemas.validation import (
    ValidationAnalysis,
    ValidationDraft,
    ValidationIssue,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStatus,
)


def test_validation_issue_schema_valid():
    issue = ValidationIssue(
        category=ValidationIssueCategory.UNSUPPORTED_CLAIM,
        severity=ValidationSeverity.MEDIUM,
        description="Market size assertion lacks empirical source evidence.",
        affected_stages=[AnalysisStage.MARKET_RESEARCH],
        evidence_ids=["src-1"],
        suggestion="Verify against broader industry data.",
    )
    assert issue.category == ValidationIssueCategory.UNSUPPORTED_CLAIM
    assert issue.severity == ValidationSeverity.MEDIUM
    assert issue.evidence_ids == ["src-1"]


def test_validation_draft_schema_valid():
    draft = ValidationDraft(
        executive_assessment="Overall sound, but financial growth assumption is aggressive.",
        issues=[
            ValidationIssue(
                category=ValidationIssueCategory.FINANCIAL_ANOMALY,
                severity=ValidationSeverity.LOW,
                description="Year 1 customer acquisition rate exceeds benchmark.",
                affected_stages=[AnalysisStage.FINANCE],
            )
        ],
    )
    assert len(draft.issues) == 1


def test_validation_analysis_schema_valid():
    analysis = ValidationAnalysis(
        status=ValidationStatus.PASSED,
        executive_assessment="Rigorous and grounded.",
        issues=[],
        can_proceed=True,
    )
    assert analysis.status == ValidationStatus.PASSED
    assert analysis.can_proceed is True
