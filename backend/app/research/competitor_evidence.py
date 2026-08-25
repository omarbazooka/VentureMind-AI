from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.research.evidence import (
    ResearchEvidenceLedger,
    ResearchEvidenceLedgerError,
    UnknownEvidenceSourceError,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CompetitorFinding,
    ResearchEvidenceQuality,
)


class CompetitorEvidenceVerificationError(
    ResearchEvidenceLedgerError
):
    pass


class CompetitorAnalysisDraft(BaseModel):
    """
    AI-facing competitor synthesis.

    The LLM may reason about competitor findings
    and reference controlled source IDs, but it
    does not own canonical source metadata.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    findings: list[
        CompetitorFinding
    ] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_quality: (
        ResearchEvidenceQuality
    )

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_draft(
        self,
    ) -> "CompetitorAnalysisDraft":
        if (
            not self.findings
            and self.evidence_quality
            != ResearchEvidenceQuality.INSUFFICIENT
        ):
            raise ValueError(
                "A Competitor draft without "
                "findings must be marked "
                "INSUFFICIENT"
            )

        if (
            self.evidence_quality
            == ResearchEvidenceQuality.INSUFFICIENT
            and not self.limitations
        ):
            raise ValueError(
                "Insufficient Competitor "
                "evidence must explain its "
                "limitations"
            )

        return self


def _collect_claimed_source_ids(
    findings: list[
        CompetitorFinding
    ],
) -> list[str]:
    claimed_source_ids: list[str] = []
    seen_source_ids: set[str] = set()

    for finding in findings:
        if (
            finding.is_numerical
            and not finding.evidence_source_ids
        ):
            raise (
                CompetitorEvidenceVerificationError(
                    "Numerical Competitor "
                    "findings must reference "
                    "controlled evidence"
                )
            )

        for source_id in (
            finding.evidence_source_ids
        ):
            if source_id in seen_source_ids:
                continue

            seen_source_ids.add(
                source_id
            )

            claimed_source_ids.append(
                source_id
            )

    return claimed_source_ids


def finalize_competitor_analysis(
    *,
    draft: CompetitorAnalysisDraft,
    evidence_ledger: ResearchEvidenceLedger,
) -> CompetitorAnalysis:
    if (
        evidence_ledger.stage
        != (
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    ):
        raise (
            CompetitorEvidenceVerificationError(
                "Competitor analysis requires "
                "a COMPETITOR_INTELLIGENCE "
                "evidence ledger"
            )
        )

    if not evidence_ledger.search_queries:
        raise (
            CompetitorEvidenceVerificationError(
                "Competitor intelligence must "
                "attempt controlled research "
                "before finalization"
            )
        )

    claimed_source_ids = (
        _collect_claimed_source_ids(
            draft.findings
        )
    )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not claimed_source_ids
    ):
        raise (
            CompetitorEvidenceVerificationError(
                "A non-insufficient Competitor "
                "analysis must cite controlled "
                "evidence"
            )
        )

    try:
        canonical_sources = (
            evidence_ledger.get_sources(
                claimed_source_ids
            )
        )

    except UnknownEvidenceSourceError as exc:
        raise (
            CompetitorEvidenceVerificationError(
                "Competitor analysis referenced "
                "evidence that was not returned "
                "by a controlled research tool"
            )
        ) from exc

    return CompetitorAnalysis(
        summary=draft.summary,
        findings=draft.findings,
        evidence_sources=canonical_sources,
        evidence_quality=(
            draft.evidence_quality
        ),
        limitations=draft.limitations,
    )
