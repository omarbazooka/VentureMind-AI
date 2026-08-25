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

from app.crews.customer_intelligence.runtime import (
    build_customer_intelligence_runner,
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
            .CUSTOMER_INTELLIGENCE
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


def validate_smoke_result(
    *,
    result,
    runner,
) -> None:
    search_queries = (
        runner.evidence_ledger.search_queries
    )

    if not search_queries:
        raise RuntimeError(
            "Customer intelligence completed "
            "without controlled web research"
        )

    if len(search_queries) > 3:
        raise RuntimeError(
            "Customer intelligence exceeded "
            "the 3-search hard limit budget"
        )

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
            "Final Customer evidence IDs "
            "do not match claimed citations"
        )

    if (
        result.evidence_quality
        != ResearchEvidenceQuality.INSUFFICIENT
        and not result.evidence_sources
    ):
        raise RuntimeError(
            "Non-insufficient Customer result "
            "has no verified evidence sources"
        )

    for finding in result.findings:
        if (
            finding.claim_kind == ResearchClaimKind.OBSERVED
            and not finding.evidence_source_ids
        ):
            raise RuntimeError(
                f"Observed Customer finding has no evidence source ID: {finding.statement}"
            )

        if (
            finding.is_numerical
            and not finding.evidence_source_ids
        ):
            raise RuntimeError(
                f"Numerical Customer finding has no evidence source ID: {finding.statement}"
            )

    for source in result.evidence_sources:
        if source.retrieved_at is None:
            raise RuntimeError(
                "Verified customer evidence "
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
                "Final Customer source metadata "
                "does not match Evidence Ledger"
            )


def main() -> None:
    runner = (
        build_customer_intelligence_runner()
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

    print("\nCUSTOMER RESEARCH PERFORMANCE:")
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
    print(
        "- evidence_quality: "
        f"{result.evidence_quality.value}"
    )
    print(
        "- finding_count: "
        f"{len(result.findings)}"
    )
    print(
        "- source_count: "
        f"{len(result.evidence_sources)}"
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

    print("\nCUSTOMER FINDINGS BY CATEGORY:")
    category_map = {}
    for finding in result.findings:
        cat = finding.category.value
        category_map.setdefault(cat, []).append(finding)

    for cat, findings in category_map.items():
        print(f"\n[{cat}] ({len(findings)} findings):")
        for f in findings:
            sources_str = ", ".join(f.evidence_source_ids) if f.evidence_source_ids else "None"
            num_str = " (NUMERICAL)" if f.is_numerical else ""
            print(
                f"  - [{f.claim_kind.value}]{num_str} "
                f"[{sources_str}] (conf: {f.confidence}) {f.statement}"
            )

    print("\nLIMITATIONS:")
    for lim in result.limitations:
        print(f"- {lim}")


if __name__ == "__main__":
    main()
