import pytest
from pydantic import ValidationError

from app.schemas.research import (
    CustomerAnalysis,
    CustomerFinding,
    CustomerFindingCategory,
    EvidenceProvenance,
    MarketAnalysis,
    MarketFinding,
    MarketFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
)


def make_source(
    source_id: str = "web-1",
) -> ResearchEvidenceSource:
    return ResearchEvidenceSource(
        source_id=source_id,
        provenance=(
            EvidenceProvenance.WEB
        ),
        title="Example market source",
        url="https://example.com/report",
        excerpt=(
            "Example evidence text."
        ),
    )


def test_market_analysis_accepts_supported_finding():
    result = MarketAnalysis(
        summary="Demand signals exist.",
        findings=[
            MarketFinding(
                category=(
                    MarketFindingCategory
                    .DEMAND_SIGNAL
                ),
                statement=(
                    "Gym software adoption "
                    "shows demand signals."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .OBSERVED
                ),
                confidence=0.8,
                evidence_source_ids=[
                    "web-1"
                ],
            )
        ],
        evidence_sources=[
            make_source()
        ],
        evidence_quality=(
            ResearchEvidenceQuality
            .MODERATE
        ),
    )

    assert len(result.findings) == 1


def test_observed_finding_requires_evidence():
    with pytest.raises(
        ValidationError
    ):
        MarketFinding(
            category=(
                MarketFindingCategory
                .DEMAND_SIGNAL
            ),
            statement="Demand exists.",
            claim_kind=(
                ResearchClaimKind
                .OBSERVED
            ),
            confidence=0.7,
            evidence_source_ids=[],
        )


def test_result_rejects_unknown_source_reference():
    with pytest.raises(
        ValidationError
    ):
        MarketAnalysis(
            summary="Market result.",
            findings=[
                MarketFinding(
                    category=(
                        MarketFindingCategory
                        .TREND
                    ),
                    statement=(
                        "Digital adoption "
                        "is increasing."
                    ),
                    claim_kind=(
                        ResearchClaimKind
                        .OBSERVED
                    ),
                    confidence=0.8,
                    evidence_source_ids=[
                        "missing-source"
                    ],
                )
            ],
            evidence_sources=[
                make_source()
            ],
            evidence_quality=(
                ResearchEvidenceQuality
                .MODERATE
            ),
        )


def test_result_rejects_duplicate_source_ids():
    with pytest.raises(
        ValidationError
    ):
        MarketAnalysis(
            summary="Market result.",
            findings=[
                MarketFinding(
                    category=(
                        MarketFindingCategory
                        .TREND
                    ),
                    statement="A trend exists.",
                    claim_kind=(
                        ResearchClaimKind
                        .OBSERVED
                    ),
                    confidence=0.8,
                    evidence_source_ids=[
                        "web-1"
                    ],
                )
            ],
            evidence_sources=[
                make_source("web-1"),
                make_source("web-1"),
            ],
            evidence_quality=(
                ResearchEvidenceQuality
                .MODERATE
            ),
        )


def test_customer_inference_is_distinct_from_observation():
    result = CustomerAnalysis(
        summary=(
            "Customer behavior is "
            "partly inferred."
        ),
        findings=[
            CustomerFinding(
                category=(
                    CustomerFindingCategory
                    .BUYING_BEHAVIOR
                ),
                statement=(
                    "Owners may value "
                    "simple onboarding."
                ),
                claim_kind=(
                    ResearchClaimKind
                    .INFERRED
                ),
                confidence=0.5,
            )
        ],
        evidence_sources=[],
        evidence_quality=(
            ResearchEvidenceQuality.WEAK
        ),
        limitations=[
            "Buying behavior is inferred."
        ],
    )

    assert (
        result.findings[0].claim_kind
        == ResearchClaimKind.INFERRED
    )


def test_insufficient_evidence_is_valid():
    result = MarketAnalysis(
        summary=(
            "Reliable evidence was "
            "insufficient."
        ),
        findings=[],
        evidence_sources=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "No reliable market sources "
            "were available."
        ],
    )

    assert result.findings == []