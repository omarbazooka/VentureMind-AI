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
    CustomerAnalysis,
    CustomerFinding,
    CustomerFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceQuality,
)


DECISION_CRITICAL_CUSTOMER_CATEGORIES = {
    CustomerFindingCategory.PAIN_POINT,
    CustomerFindingCategory.ALTERNATIVE,
    CustomerFindingCategory.BUYING_BEHAVIOR,
    CustomerFindingCategory.DEMAND_SIGNAL,
}


def _has_decision_critical_observed_findings(
    findings: list[CustomerFinding],
) -> bool:
    for finding in findings:
        if (
            finding.claim_kind == ResearchClaimKind.OBSERVED
            and finding.category in DECISION_CRITICAL_CUSTOMER_CATEGORIES
        ):
            return True
        if (
            finding.is_numerical
            and finding.claim_kind == ResearchClaimKind.OBSERVED
        ):
            return True
    return False


class CustomerEvidenceVerificationError(
    ResearchEvidenceLedgerError
):
    pass


class CustomerAnalysisDraft(BaseModel):
    """AI-facing Customer synthesis without source metadata authority."""

    model_config = ConfigDict(
        extra="forbid"
    )

    summary: str = Field(
        min_length=1,
        max_length=5000,
    )

    findings: list[CustomerFinding] = Field(
        default_factory=list,
        max_length=30,
    )

    evidence_quality: ResearchEvidenceQuality

    limitations: list[str] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_draft(
        self,
    ) -> "CustomerAnalysisDraft":
        if (
            not self.findings
            and self.evidence_quality
            != ResearchEvidenceQuality.INSUFFICIENT
        ):
            raise ValueError(
                "A Customer draft without findings "
                "must be marked INSUFFICIENT"
            )

        if (
            self.evidence_quality
            == ResearchEvidenceQuality.INSUFFICIENT
            and not self.limitations
        ):
            raise ValueError(
                "Insufficient Customer evidence "
                "must explain its limitations"
            )

        return self


def _collect_claimed_source_ids(
    findings: list[CustomerFinding],
) -> list[str]:
    claimed_source_ids: list[str] = []
    seen_source_ids: set[str] = set()

    for finding in findings:
        if (
            finding.is_numerical
            and not finding.evidence_source_ids
        ):
            raise CustomerEvidenceVerificationError(
                "Numerical Customer findings must "
                "reference controlled evidence"
            )

        for source_id in (
            finding.evidence_source_ids
        ):
            if source_id in seen_source_ids:
                continue

            seen_source_ids.add(source_id)
            claimed_source_ids.append(
                source_id
            )

    return claimed_source_ids


def finalize_customer_analysis(
    *,
    draft: CustomerAnalysisDraft,
    evidence_ledger: ResearchEvidenceLedger,
) -> CustomerAnalysis:
    if (
        evidence_ledger.stage
        != AnalysisStage.CUSTOMER_INTELLIGENCE
    ):
        raise CustomerEvidenceVerificationError(
            "Customer analysis requires a "
            "CUSTOMER_INTELLIGENCE evidence ledger"
        )

    if not evidence_ledger.search_queries:
        raise CustomerEvidenceVerificationError(
            "Customer intelligence must "
            "attempt controlled research "
            "before finalization"
        )

    claimed_source_ids = (
        _collect_claimed_source_ids(
            draft.findings
        )
    )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and _has_decision_critical_observed_findings(draft.findings)
        and not evidence_ledger.page_retrieval_urls
    ):
        raise CustomerEvidenceVerificationError(
            "Decision-critical observed Customer findings "
            "require controlled detailed-page evidence"
        )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not claimed_source_ids
    ):
        raise CustomerEvidenceVerificationError(
            "A non-insufficient Customer analysis "
            "must cite controlled evidence"
        )

    try:
        canonical_sources = (
            evidence_ledger.get_sources(
                claimed_source_ids
            )
        )
    except UnknownEvidenceSourceError as exc:
        raise CustomerEvidenceVerificationError(
            "Customer analysis referenced evidence "
            "that was not returned by a controlled "
            "research tool"
        ) from exc

    return CustomerAnalysis(
        summary=draft.summary,
        findings=draft.findings,
        evidence_sources=canonical_sources,
        evidence_quality=(
            draft.evidence_quality
        ),
        limitations=draft.limitations,
    )
