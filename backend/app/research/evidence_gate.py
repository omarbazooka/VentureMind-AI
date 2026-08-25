from app.schemas.analysis import (
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchGateIssueCode,
    ResearchStageGateAssessment,
    ResearchStageGateInput,
)


DEFAULT_MAX_RESEARCH_ATTEMPTS = 2

REQUIRED_RESEARCH_STAGES = (
    AnalysisStage.MARKET_RESEARCH,
    AnalysisStage.COMPETITOR_INTELLIGENCE,
    AnalysisStage.CUSTOMER_INTELLIGENCE,
)

ACCEPTABLE_EVIDENCE_QUALITIES = {
    ResearchEvidenceQuality.STRONG,
    ResearchEvidenceQuality.MODERATE,
}


class ResearchEvidenceGateError(RuntimeError):
    pass


class ResearchEvidenceGateInputError(
    ResearchEvidenceGateError
):
    pass


class ResearchEvidenceGateNotReadyError(
    ResearchEvidenceGateError
):
    pass


def _assessment_for_stage(
    *,
    stage_input: ResearchStageGateInput,
    max_attempts: int,
) -> ResearchStageGateAssessment:
    issue_codes: list[ResearchGateIssueCode] = []
    retry_eligible = False

    if stage_input.stage_status == AnalysisStageStatus.FAILED:
        issue_codes.append(
            ResearchGateIssueCode.STAGE_FAILED
        )

        if stage_input.attempt < max_attempts:
            retry_eligible = True
        else:
            issue_codes.append(
                ResearchGateIssueCode.RETRY_EXHAUSTED
            )

        return ResearchStageGateAssessment(
            stage=stage_input.stage,
            attempt=stage_input.attempt,
            stage_status=stage_input.stage_status,
            evidence_quality=None,
            limitations=stage_input.limitations,
            retry_eligible=retry_eligible,
            issue_codes=issue_codes,
        )

    if stage_input.stage_status != AnalysisStageStatus.COMPLETED:
        raise ResearchEvidenceGateNotReadyError(
            "Research Evidence Gate requires every latest stage attempt "
            "to be COMPLETED or FAILED"
        )

    quality = stage_input.evidence_quality
    if quality is None:
        raise ResearchEvidenceGateInputError(
            "Completed research stages must include evidence quality"
        )

    if quality in ACCEPTABLE_EVIDENCE_QUALITIES:
        pass
    elif quality == ResearchEvidenceQuality.WEAK:
        issue_codes.append(
            ResearchGateIssueCode.WEAK_EVIDENCE
        )

        if stage_input.attempt < max_attempts:
            retry_eligible = True
        else:
            issue_codes.append(
                ResearchGateIssueCode.RETRY_EXHAUSTED
            )
    elif quality == ResearchEvidenceQuality.INSUFFICIENT:
        issue_codes.append(
            ResearchGateIssueCode.INSUFFICIENT_EVIDENCE
        )
    else:
        raise ResearchEvidenceGateInputError(
            f"Unsupported evidence quality: {quality}"
        )

    return ResearchStageGateAssessment(
        stage=stage_input.stage,
        attempt=stage_input.attempt,
        stage_status=stage_input.stage_status,
        evidence_quality=quality,
        limitations=stage_input.limitations,
        retry_eligible=retry_eligible,
        issue_codes=issue_codes,
    )


def evaluate_research_evidence_gate(
    *,
    stages: list[ResearchStageGateInput],
    max_attempts: int = DEFAULT_MAX_RESEARCH_ATTEMPTS,
) -> ResearchEvidenceGateResult:
    if max_attempts < 1:
        raise ValueError(
            "max_attempts must be at least 1"
        )

    by_stage: dict[AnalysisStage, ResearchStageGateInput] = {}

    for stage_input in stages:
        if stage_input.stage in by_stage:
            raise ResearchEvidenceGateInputError(
                "Research Evidence Gate received duplicate stage input: "
                f"{stage_input.stage.value}"
            )

        by_stage[stage_input.stage] = stage_input

    missing_stages = [
        stage
        for stage in REQUIRED_RESEARCH_STAGES
        if stage not in by_stage
    ]

    if missing_stages:
        raise ResearchEvidenceGateInputError(
            "Research Evidence Gate is missing required stages: "
            + ", ".join(
                stage.value
                for stage in missing_stages
            )
        )

    assessments = [
        _assessment_for_stage(
            stage_input=by_stage[stage],
            max_attempts=max_attempts,
        )
        for stage in REQUIRED_RESEARCH_STAGES
    ]

    retry_stages = [
        assessment.stage
        for assessment in assessments
        if assessment.retry_eligible
    ]

    insufficient_stages = [
        assessment.stage
        for assessment in assessments
        if (
            ResearchGateIssueCode.INSUFFICIENT_EVIDENCE
            in assessment.issue_codes
            or ResearchGateIssueCode.RETRY_EXHAUSTED
            in assessment.issue_codes
        )
    ]

    if retry_stages:
        decision = ResearchGateDecision.RETRY
        can_proceed = False
    elif insufficient_stages:
        decision = ResearchGateDecision.INSUFFICIENT
        can_proceed = True
    else:
        decision = ResearchGateDecision.ACCEPT
        can_proceed = True

    return ResearchEvidenceGateResult(
        decision=decision,
        can_proceed=can_proceed,
        assessments=assessments,
        retry_stages=retry_stages,
        insufficient_stages=insufficient_stages,
    )
