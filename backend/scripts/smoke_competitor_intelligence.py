import sys
import time
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
                    "target_country": "Egypt",
                    "revenue_model": (
                        "Monthly SaaS subscription"
                    ),
                },
                profile_metadata={},
                unknown_fields=[],
            )
        ),
    )


from app.research.competitor_evidence import (
    PROHIBITED_PMF_PATTERN,
    UNAVAILABLE_PRICING_PATTERN,
    UNSUPPORTED_ABSENCE_PATTERN,
)


def _validate_detail(
    detail,
) -> None:
    if (
        detail.claim_kind
        == ResearchClaimKind.OBSERVED
        and not detail.evidence_source_ids
    ):
        raise RuntimeError(
            "Observed competitor detail "
            "has no evidence source"
        )

    if (
        detail.is_numerical
        and not detail.evidence_source_ids
    ):
        raise RuntimeError(
            "Numerical competitor detail "
            "has no evidence source"
        )

    if (
        detail.claim_kind
        == ResearchClaimKind.INFERRED
        and UNSUPPORTED_ABSENCE_PATTERN.search(
            detail.statement
        )
    ):
        raise RuntimeError(
            "Inferred competitor detail contains "
            f"unsupported absence language: {detail.statement}"
        )


def validate_smoke_result(
    *,
    result,
    runner,
) -> None:
    if PROHIBITED_PMF_PATTERN.search(result.summary):
        raise RuntimeError(
            "Competitor summary contains prohibited PMF phrasing: "
            f"{result.summary}"
        )

    search_queries = (
        runner.evidence_ledger.search_queries
    )

    if not search_queries:
        raise RuntimeError(
            "Competitor intelligence completed "
            "without controlled web research"
        )

    if len(search_queries) > 2:
        raise RuntimeError(
            "Competitor intelligence exceeded "
            "the two-search latency budget"
        )

    if (
        result.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
    ):
        if not result.competitors:
            raise RuntimeError(
                "Non-insufficient Competitor "
                "result has no competitor cards"
            )

        if not (
            runner
            .evidence_ledger
            .page_retrieval_urls
        ):
            raise RuntimeError(
                "Detailed competitor result was "
                "created without page retrieval"
            )

    if len(result.competitors) > 5:
        raise RuntimeError(
            "Competitor result exceeded five "
            "frontend-ready profiles"
        )

    claimed_source_ids = {
        source_id
        for finding in result.findings
        for source_id
        in finding.evidence_source_ids
    }

    for competitor in result.competitors:
        claimed_source_ids.add(
            competitor.primary_source_id
        )

        details = [
            *competitor.strengths,
            *competitor.weaknesses,
        ]

        if competitor.pricing is not None:
            if UNAVAILABLE_PRICING_PATTERN.search(
                competitor.pricing.statement
            ):
                raise RuntimeError(
                    "Competitor pricing contains "
                    "placeholder statement: "
                    f"{competitor.pricing.statement}"
                )

        for optional_detail in (
            competitor.pricing,
            competitor.positioning,
            competitor.target_audience,
            competitor.geography,
        ):
            if optional_detail is not None:
                details.append(optional_detail)

        for detail in details:
            _validate_detail(detail)
            claimed_source_ids.update(
                detail.evidence_source_ids
            )

    finalized_source_ids = {
        source.source_id
        for source in result.evidence_sources
    }

    if claimed_source_ids != finalized_source_ids:
        raise RuntimeError(
            "Final Competitor evidence IDs "
            "do not match claimed citations"
        )

    if (
        result.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not result.evidence_sources
    ):
        raise RuntimeError(
            "Non-insufficient Competitor result "
            "has no verified evidence sources"
        )

    for source in result.evidence_sources:
        if source.retrieved_at is None:
            raise RuntimeError(
                "Verified competitor evidence "
                "is missing retrieval timestamp"
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
            or source.excerpt
            != ledger_source.excerpt
        ):
            raise RuntimeError(
                "Final Competitor source metadata "
                "does not match Evidence Ledger"
            )


def main() -> None:
    runner = (
        build_competitor_intelligence_runner()
    )

    claim = build_smoke_claim()

    started_at = time.perf_counter()

    result = runner(claim)

    elapsed_seconds = (
        time.perf_counter()
        - started_at
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

    print("\nRESEARCH PERFORMANCE:")
    print(
        f"- elapsed_seconds: "
        f"{elapsed_seconds:.2f}"
    )
    print(
        "- search_count: "
        f"{len(runner.evidence_ledger.search_queries)}"
    )
    print(
        "- page_retrieval_count: "
        f"{len(runner.evidence_ledger.page_retrieval_urls)}"
    )

    print("\nVERIFIED SEARCH QUERIES:")
    for query in (
        runner.evidence_ledger.search_queries
    ):
        print(f"- {query}")

    print("\nVERIFIED PAGE RETRIEVALS:")
    for url in (
        runner.evidence_ledger.page_retrieval_urls
    ):
        print(f"- {url}")

    print("\nVERIFIED SOURCE URLS:")
    for source in result.evidence_sources:
        print(
            f"- {source.source_id}: {source.url}"
        )

    print("\nCOMPETITOR CARDS:")
    for competitor in result.competitors:
        print(
            f"\n- {competitor.name} "
            f"[{competitor.relationship.value}]"
        )
        print(
            "  relevance: "
            f"{competitor.relevance_summary}"
        )

        if competitor.strengths:
            print("  strengths:")
            for strength in competitor.strengths:
                print(
                    "    - "
                    f"[{strength.claim_kind.value}] "
                    f"{strength.statement}"
                )

        if competitor.weaknesses:
            print("  weaknesses:")
            for weakness in competitor.weaknesses:
                print(
                    "    - "
                    f"[{weakness.claim_kind.value}] "
                    f"{weakness.statement}"
                )

        if competitor.pricing is not None:
            print(
                "  pricing: "
                f"[{competitor.pricing.claim_kind.value}] "
                f"{competitor.pricing.statement}"
            )


if __name__ == "__main__":
    main()
