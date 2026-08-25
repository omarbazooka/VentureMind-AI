from app.core.config import settings
from app.crews.competitor_intelligence.crew import (
    CompetitorIntelligenceCrewRunner,
)
from app.llm.crewai_adapter import (
    CrewAILLMGatewayAdapter,
)
from app.llm.gateway import (
    LLMGateway,
)
from app.research.evidence import (
    ResearchEvidenceLedger,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.tools.crewai import (
    ControlledWebSearchTool,
)
from app.tools.gateway import (
    ToolGateway,
    WebSearchProvider,
)
from app.tools.providers.firecrawl import (
    FirecrawlWebSearchProvider,
)


def build_competitor_intelligence_runner(
    *,
    llm_gateway: LLMGateway | None = None,
    web_search_provider: (
        WebSearchProvider | None
    ) = None,
    model: str | None = None,
) -> CompetitorIntelligenceCrewRunner:
    """
    Build one isolated Competitor Intelligence
    stage runtime.
    """

    resolved_llm_gateway = (
        llm_gateway
        if llm_gateway is not None
        else LLMGateway()
    )

    resolved_search_provider = (
        web_search_provider
        if web_search_provider is not None
        else FirecrawlWebSearchProvider()
    )

    resolved_model = (
        model
        if model is not None
        else (
            settings
            .competitor_intelligence_model
        )
    )

    evidence_ledger = (
        ResearchEvidenceLedger(
            stage=(
                AnalysisStage
                .COMPETITOR_INTELLIGENCE
            )
        )
    )

    tool_gateway = ToolGateway(
        web_search_provider=(
            resolved_search_provider
        )
    )

    research_tool = (
        ControlledWebSearchTool(
            gateway=tool_gateway,
            stage=(
                AnalysisStage
                .COMPETITOR_INTELLIGENCE
            ),
            evidence_ledger=evidence_ledger,
            max_usage_count=4,
        )
    )

    crewai_llm = (
        CrewAILLMGatewayAdapter(
            gateway=resolved_llm_gateway,
            model=resolved_model,
        )
    )

    return (
        CompetitorIntelligenceCrewRunner(
            llm=crewai_llm,
            research_tool=research_tool,
            evidence_ledger=(
                evidence_ledger
            ),
        )
    )