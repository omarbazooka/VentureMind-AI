import re

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
    ResearchEvidenceSource,
)


DECISION_CRITICAL_CUSTOMER_CATEGORIES = {
    CustomerFindingCategory.PAIN_POINT,
    CustomerFindingCategory.ALTERNATIVE,
    CustomerFindingCategory.BUYING_BEHAVIOR,
    CustomerFindingCategory.DEMAND_SIGNAL,
}

VENDOR_SENSITIVE_CUSTOMER_CATEGORIES = {
    CustomerFindingCategory.PAIN_POINT,
    CustomerFindingCategory.ALTERNATIVE,
    CustomerFindingCategory.BUYING_BEHAVIOR,
    CustomerFindingCategory.DEMAND_SIGNAL,
}

DIRECT_CUSTOMER_EVIDENCE_PATTERN = re.compile(
    r"\b("
    r"survey(?:ed|s)?|interview(?:ed|s)?|respondents?|participants?|"
    r"customer reviews?|owner reviews?|operator reviews?|"
    r"owners?\s+report|operators?\s+report|"
    r"practitioner discussions?|forum discussions?|reddit|"
    r"case stud(?:y|ies)"
    r")\b",
    re.IGNORECASE,
)

VENDOR_PRODUCT_PATTERN = re.compile(
    r"\b(software|platform|solution|system|app|saas|service)\b",
    re.IGNORECASE,
)

VENDOR_COMMERCIAL_PATTERN = re.compile(
    r"\b("
    r"starting\s+at|starts?\s+at|pricing|plans?|"
    r"book\s+(?:a\s+)?demo|get\s+a\s+quote|get\s+started|"
    r"free\s+trial|why\s+choose|best\s+(?:software|platform|solution)|"
    r"our\s+(?:software|platform|solution|system|app|service)|"
    r"we\s+(?:help|offer|provide|build|built)|"
    r"automate\s+operations|retain\s+members|grow\s+revenue"
    r")\b"
    r"|\$\s?\d+(?:\.\d+)?\s*(?:/|per)\s*(?:mo|month)",
    re.IGNORECASE,
)

SUPPLY_TO_DEMAND_PHRASE_PATTERN = re.compile(
    r"\b(?:indicat(?:e|es|ed)|suggest(?:s|ed)?|show(?:s|ed)?)\s+"
    r"(?:active\s+market\s+formation\s+and\s+vendor\s+belief\s+in\s+)?"
    r"(?:growing\s+)?(?:software\s+)?(?:customer\s+)?"
    r"(?:demand|adoption)\b",
    re.IGNORECASE,
)

VENDOR_SIDE_LIMITATION = (
    "Customer behavior and demand remain indirect where cited support "
    "comes only from vendor-authored marketing evidence."
)


def _has_decision_critical_observed_findings(
    findings: list[CustomerFinding],
) -> bool:
    for finding in findings:
        if finding.is_numerical:
            return True
        if (
            finding.claim_kind == ResearchClaimKind.OBSERVED
            and finding.category in DECISION_CRITICAL_CUSTOMER_CATEGORIES
        ):
            return True
    return False


def _is_likely_vendor_marketing_source(
    source: ResearchEvidenceSource,
) -> bool:
    text = " ".join(
        part
        for part in (
            source.title,
            source.excerpt or "",
        )
        if part
    )

    if DIRECT_CUSTOMER_EVIDENCE_PATTERN.search(text):
        return False

    return bool(
        VENDOR_PRODUCT_PATTERN.search(text)
        and VENDOR_COMMERCIAL_PATTERN.search(text)
    )


def _finding_uses_only_vendor_marketing_sources(
    *,
    finding: CustomerFinding,
    sources_by_id: dict[str, ResearchEvidenceSource],
) -> bool:
    if not finding.evidence_source_ids:
        return False

    return all(
        _is_likely_vendor_marketing_source(
            sources_by_id[source_id]
        )
        for source_id in finding.evidence_source_ids
    )


def _normalize_vendor_only_findings(
    *,
    findings: list[CustomerFinding],
    sources_by_id: dict[str, ResearchEvidenceSource],
) -> tuple[list[CustomerFinding], bool]:
    normalized_findings: list[CustomerFinding] = []
    normalized_any = False

    for finding in findings:
        if (
            finding.category in VENDOR_SENSITIVE_CUSTOMER_CATEGORIES
            and _finding_uses_only_vendor_marketing_sources(
                finding=finding,
                sources_by_id=sources_by_id,
            )
        ):
            normalized_any = True
            normalized_findings.append(
                finding.model_copy(
                    update={
                        "claim_kind": ResearchClaimKind.INFERRED,
                        "confidence": min(
                            finding.confidence,
                            0.6,
                        ),
                    }
                )
            )
            continue

        normalized_findings.append(finding)

    return normalized_findings, normalized_any


def _normalize_vendor_only_summary(
    *,
    summary: str,
    all_cited_sources_are_vendor_marketing: bool,
) -> str:
    if not all_cited_sources_are_vendor_marketing:
        return summary

    return SUPPLY_TO_DEMAND_PHRASE_PATTERN.sub(
        "show active vendor supply; direct customer demand and adoption remain unverified",
        summary,
    )


def _normalize_vendor_only_evidence_quality(
    *,
    evidence_quality: ResearchEvidenceQuality,
    all_cited_sources_are_vendor_marketing: bool,
) -> ResearchEvidenceQuality:
    if (
        all_cited_sources_are_vendor_marketing
        and evidence_quality
        in {
            ResearchEvidenceQuality.STRONG,
            ResearchEvidenceQuality.MODERATE,
        }
    ):
        return ResearchEvidenceQuality.WEAK

    return evidence_quality


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

    sources_by_id = {
        source.source_id: source
        for source in canonical_sources
    }

    normalized_findings, normalized_vendor_claims = (
        _normalize_vendor_only_findings(
            findings=draft.findings,
            sources_by_id=sources_by_id,
        )
    )

    if (
        draft.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and _has_decision_critical_observed_findings(
            normalized_findings
        )
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

    all_cited_sources_are_vendor_marketing = bool(
        canonical_sources
    ) and all(
        _is_likely_vendor_marketing_source(source)
        for source in canonical_sources
    )

    normalized_summary = _normalize_vendor_only_summary(
        summary=draft.summary,
        all_cited_sources_are_vendor_marketing=(
            all_cited_sources_are_vendor_marketing
        ),
    )

    normalized_evidence_quality = (
        _normalize_vendor_only_evidence_quality(
            evidence_quality=draft.evidence_quality,
            all_cited_sources_are_vendor_marketing=(
                all_cited_sources_are_vendor_marketing
            ),
        )
    )

    normalized_limitations = list(
        draft.limitations
    )
    if (
        normalized_vendor_claims
        and VENDOR_SIDE_LIMITATION
        not in normalized_limitations
        and len(normalized_limitations) < 20
    ):
        normalized_limitations.append(
            VENDOR_SIDE_LIMITATION
        )

    return CustomerAnalysis(
        summary=normalized_summary,
        findings=normalized_findings,
        evidence_sources=canonical_sources,
        evidence_quality=(
            normalized_evidence_quality
        ),
        limitations=normalized_limitations,
    )
