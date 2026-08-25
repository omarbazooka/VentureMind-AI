import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(
        Path(__file__)
        .resolve()
        .parents[1]
    ),
)

from app.crews.competitor_intelligence.runtime import (
    build_competitor_intelligence_runner,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchClaimKind,
    ResearchEvidenceQuality,
    ResearchStageClaim,
)


def build_smoke_claim(
) -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        ),
        attempt=1,
        profile_snapshot=(
            AnalysisProfileSnapshot(
                readiness=(
                    ProfileReadinessStatus
                    .READY_FOR_ANALYSIS
                ),
                profile_data={
                    "idea_description": (
                        "A SaaS platform for "
                        "independent gyms to "
                        "manage memberships, "
                        "payments, classes, "
                        "and customer retention."
                    ),
                    "problem": (
                        "Independent gym owners "
                        "often manage memberships, "
                        "payments, schedules, and "
                        "member communication "
                        "through fragmented manual "
                        "tools."
                    ),
                    "proposed_solution": (
                        "One gym management SaaS "
                        "platform combining member "
                        "management, billing, "
                        "class scheduling, and "
                        "retention workflows."
                    ),
                    "target_customers": [
                        "Independent gym owners"
                    ],
                    "target_country": (
                        "Egypt"
                    ),
                    "revenue_model": (
                        "Monthly SaaS "
                        "subscription"
                    ),
                },
                profile_metadata={},
                unknown_fields=[],
            )
        ),
    )


def validate_smoke_result(
    *,
    result,
    runner,
) -> None:
    if not (
        runner
        .evidence_ledger
        .search_queries
    ):
        raise RuntimeError(
            "Competitor intelligence "
            "completed without attempting "
            "controlled web research"
        )

    claimed_source_ids = {
        source_id
        for finding in result.findings
        for source_id
        in finding.evidence_source_ids
    }

    finalized_source_ids = {
        source.source_id
        for source
        in result.evidence_sources
    }

    if (
        claimed_source_ids
        != finalized_source_ids
    ):
        raise RuntimeError(
            "Final Competitor evidence "
            "IDs do not match finding "
            "citations"
        )

    if (
        result.evidence_quality
        != (
            ResearchEvidenceQuality
            .INSUFFICIENT
        )
        and not result.evidence_sources
    ):
        raise RuntimeError(
            "Non-insufficient Competitor "
            "result has no verified "
            "evidence sources"
        )

    for finding in result.findings:
        if (
            finding.claim_kind
            == ResearchClaimKind.OBSERVED
            and not (
                finding
                .evidence_source_ids
            )
        ):
            raise RuntimeError(
                "Observed Competitor finding "
                "has no evidence source"
            )

        if (
            finding.is_numerical
            and not (
                finding
                .evidence_source_ids
            )
        ):
            raise RuntimeError(
                "Numerical Competitor "
                "finding has no evidence "
                "source"
            )

    for source in result.evidence_sources:
        if source.retrieved_at is None:
            raise RuntimeError(
                "Verified competitor WEB "
                "evidence is missing its "
                "retrieval timestamp"
            )

        ledger_source = (
            runner
            .evidence_ledger
            .get_source(
                source.source_id
            )
        )

        if (
            str(source.url)
            != str(ledger_source.url)
        ):
            raise RuntimeError(
                "Final Competitor source "
                "URL does not match the "
                "Evidence Ledger"
            )

        if (
            source.title
            != ledger_source.title
        ):
            raise RuntimeError(
                "Final Competitor source "
                "title does not match the "
                "Evidence Ledger"
            )

        if (
            source.excerpt
            != ledger_source.excerpt
        ):
            raise RuntimeError(
                "Final Competitor source "
                "excerpt does not match "
                "the Evidence Ledger"
            )


def main() -> None:
    runner = (
        build_competitor_intelligence_runner()
    )

    claim = build_smoke_claim()

    result = runner(
        claim
    )

    validate_smoke_result(
        result=result,
        runner=runner,
    )

    print(
        result.model_dump_json(
            indent=2
        )
    )

    print(
        "\nVERIFIED SEARCH QUERIES:"
    )

    for query in (
        runner
        .evidence_ledger
        .search_queries
    ):
        print(
            f"- {query}"
        )

    print(
        "\nVERIFIED SOURCE URLS:"
    )

    for source in (
        result.evidence_sources
    ):
        print(
            f"- {source.source_id}: "
            f"{source.url}"
        )

    print(
        "\nCOMPETITOR FINDINGS:"
    )

    for finding in result.findings:
        print(
            f"- [{finding.category.value}] "
            f"[{finding.claim_kind.value}] "
            f"{finding.statement}"
        )


if __name__ == "__main__":
    main()
