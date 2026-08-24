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


def main() -> None:
    runner = (
        build_market_research_runner()
    )

    claim = build_smoke_claim()

    result = runner(
        claim
    )

    print(
        result.model_dump_json(
            indent=2
        )
    )


if __name__ == "__main__":
    main()