from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

import re

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
    CompetitorDetail,
    CompetitorFinding,
    CompetitorProfile,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)


UNSUPPORTED_ABSENCE_PATTERN = re.compile(
    r"\b("
    r"lacks?|lacking|"
    r"does\s+not\s+(have|offer|support|include|provide|feature)|"
    r"doesn['’]t\s+(have|offer|support|include|provide|feature)|"
    r"missing"
    r")\b",
    re.IGNORECASE,
)

UNAVAILABLE_PRICING_PATTERN = re.compile(
    r"\b("
    r"pricing\s+(is\s+|was\s+)?(not\s+|un)(published|available|disclosed|publicly|known)|"
    r"pricing\s+is\s+not\s+publicly\s+available|"
    r"no\s+(public|published)\s+pricing|"
    r"pricing\s+info(rmation)?\s+(is\s+)?not\s+available"
    r")\b",
    re.IGNORECASE,
)


class CompetitorEvidenceVerificationError(
    ResearchEvidenceLedgerError
):
    pass


class CompetitorAnalysisDraft(BaseModel):
    """AI-facing competitor synthesis without source metadata authority."""

    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    competitors: list[
        CompetitorProfile
    ] = Field(
        default_factory=list,
        max_length=5,
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
            and not self.competitors
            and self.evidence_quality
            != ResearchEvidenceQuality.INSUFFICIENT
        ):
            raise ValueError(
                "A Competitor draft without "
                "findings or competitor profiles "
                "must be marked INSUFFICIENT"
            )

        if (
            self.evidence_quality
            != ResearchEvidenceQuality.INSUFFICIENT
            and not self.competitors
        ):
            raise ValueError(
                "A non-insufficient Competitor "
                "draft must include competitor "
                "profiles"
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


def _append_unique_source_id(
    *,
    source_id: str,
    claimed_source_ids: list[str],
    seen_source_ids: set[str],
) -> None:
    if source_id in seen_source_ids:
        return

    seen_source_ids.add(source_id)
    claimed_source_ids.append(source_id)


def _collect_detail_source_ids(
    *,
    detail: CompetitorDetail,
    claimed_source_ids: list[str],
    seen_source_ids: set[str],
) -> None:
    if (
        detail.is_numerical
        and not detail.evidence_source_ids
    ):
        raise CompetitorEvidenceVerificationError(
            "Numerical Competitor details must "
            "reference controlled evidence"
        )

    for source_id in detail.evidence_source_ids:
        _append_unique_source_id(
            source_id=source_id,
            claimed_source_ids=(
                claimed_source_ids
            ),
            seen_source_ids=seen_source_ids,
        )


def _collect_claimed_source_ids(
    *,
    findings: list[CompetitorFinding],
    competitors: list[CompetitorProfile],
) -> list[str]:
    claimed_source_ids: list[str] = []
    seen_source_ids: set[str] = set()

    for finding in findings:
        if (
            finding.is_numerical
            and not finding.evidence_source_ids
        ):
            raise CompetitorEvidenceVerificationError(
                "Numerical Competitor findings "
                "must reference controlled evidence"
            )

        for source_id in (
            finding.evidence_source_ids
        ):
            _append_unique_source_id(
                source_id=source_id,
                claimed_source_ids=(
                    claimed_source_ids
                ),
                seen_source_ids=seen_source_ids,
            )

    for competitor in competitors:
        _append_unique_source_id(
            source_id=competitor.primary_source_id,
            claimed_source_ids=(
                claimed_source_ids
            ),
            seen_source_ids=seen_source_ids,
        )

        details = [
            *competitor.strengths,
            *competitor.weaknesses,
        ]

        for optional_detail in (
            competitor.pricing,
            competitor.positioning,
            competitor.target_audience,
            competitor.geography,
        ):
            if optional_detail is not None:
                details.append(optional_detail)

        for detail in details:
            _collect_detail_source_ids(
                detail=detail,
                claimed_source_ids=(
                    claimed_source_ids
                ),
                seen_source_ids=seen_source_ids,
            )

    return claimed_source_ids


def _verify_semantic_rules(
    *,
    findings: list[CompetitorFinding],
    competitors: list[CompetitorProfile],
) -> None:
    for competitor in competitors:
        if competitor.pricing is not None:
            if UNAVAILABLE_PRICING_PATTERN.search(
                competitor.pricing.statement
            ):
                raise CompetitorEvidenceVerificationError(
                    "Unknown or unpublished pricing must be "
                    "represented as pricing=None instead of "
                    "a placeholder pricing detail"
                )

        for weakness in competitor.weaknesses:
            if (
                weakness.claim_kind == ResearchClaimKind.INFERRED
                and UNSUPPORTED_ABSENCE_PATTERN.search(
                    weakness.statement
                )
            ):
                raise CompetitorEvidenceVerificationError(
                    "Inferred competitor weaknesses must not make "
                    "unsupported absence assertions (e.g. lacks, "
                    "does not have, missing)"
                )

    for finding in findings:
        if (
            finding.claim_kind == ResearchClaimKind.INFERRED
            and UNSUPPORTED_ABSENCE_PATTERN.search(finding.statement)
        ):
            raise CompetitorEvidenceVerificationError(
                "Inferred competitor findings must not make "
                "unsupported absence assertions (e.g. lacks, "
                "does not have, missing)"
            )


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
        raise CompetitorEvidenceVerificationError(
            "Competitor analysis requires a "
            "COMPETITOR_INTELLIGENCE "
            "evidence ledger"
        )

    if not evidence_ledger.search_queries:
        raise CompetitorEvidenceVerificationError(
            "Competitor intelligence must "
            "attempt controlled research "
            "before finalization"
        )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not evidence_ledger.page_retrieval_urls
    ):
        raise CompetitorEvidenceVerificationError(
            "A non-insufficient Competitor "
            "analysis must inspect at least one "
            "detailed page through controlled "
            "page retrieval"
        )

    _verify_semantic_rules(
        findings=draft.findings,
        competitors=draft.competitors,
    )

    claimed_source_ids = (
        _collect_claimed_source_ids(
            findings=draft.findings,
            competitors=draft.competitors,
        )
    )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not claimed_source_ids
    ):
        raise CompetitorEvidenceVerificationError(
            "A non-insufficient Competitor "
            "analysis must cite controlled "
            "evidence"
        )

    try:
        canonical_sources = (
            evidence_ledger.get_sources(
                claimed_source_ids
            )
        )
    except UnknownEvidenceSourceError as exc:
        raise CompetitorEvidenceVerificationError(
            "Competitor analysis referenced "
            "evidence that was not returned "
            "by a controlled research tool"
        ) from exc

    return CompetitorAnalysis(
        summary=draft.summary,
        competitors=draft.competitors,
        findings=draft.findings,
        evidence_sources=canonical_sources,
        evidence_quality=(
            draft.evidence_quality
        ),
        limitations=draft.limitations,
    )
