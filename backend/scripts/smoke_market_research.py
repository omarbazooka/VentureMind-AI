import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from app.crews.market_research.runtime import (
    build_market_research_runner,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchEvidenceQuality,
    ResearchStageClaim,
)


def build_smoke_claim(
) -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage.MARKET_RESEARCH
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
    claimed_source_ids = {
        source_id
        for finding in result.findings
        for source_id
        in finding.evidence_source_ids
    }

    finalized_source_ids = {
        source.source_id
        for source in result.evidence_sources
    }

    if claimed_source_ids != finalized_source_ids:
        raise RuntimeError(
            "Final Market evidence IDs do not "
            "match finding citations"
        )

    if (
        result.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not result.evidence_sources
    ):
        raise RuntimeError(
            "Non-insufficient Market result "
            "has no verified evidence sources"
        )

    for source in result.evidence_sources:
        if source.retrieved_at is None:
            raise RuntimeError(
                "Verified WEB evidence is missing "
                "its retrieval timestamp"
            )

        ledger_source = (
            runner.evidence_ledger.get_source(
                source.source_id
            )
        )

        if (
            str(source.url)
            != str(ledger_source.url)
            or source.title
            != ledger_source.title
        ):
            raise RuntimeError(
                "Final Market source metadata "
                "does not match the evidence ledger"
            )


def main() -> None:
    runner = (
        build_market_research_runner()
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

    print("\nVERIFIED SEARCH QUERIES:")
    for query in (
        runner.evidence_ledger.search_queries
    ):
        print(f"- {query}")

    print("\nVERIFIED SOURCE URLS:")
    for source in result.evidence_sources:
        print(
            f"- {source.source_id}: {source.url}"
        )


if __name__ == "__main__":
    main()
