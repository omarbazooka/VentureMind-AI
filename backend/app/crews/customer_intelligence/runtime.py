from app.core.config import settings
from app.crews.customer_intelligence.crew import (
    CustomerIntelligenceCrewRunner,
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
    ControlledBatchPageRetrievalTool,
    ControlledWebSearchTool,
)
from app.tools.gateway import (
    PageRetrievalProvider,
    ToolGateway,
    WebSearchProvider,
)
from app.tools.providers.firecrawl import (
    FirecrawlPageRetrievalProvider,
    FirecrawlWebSearchProvider,
)


def build_customer_intelligence_runner(
    *,
    llm_gateway: LLMGateway | None = None,
    web_search_provider: (
        WebSearchProvider | None
    ) = None,
    page_retrieval_provider: (
        PageRetrievalProvider | None
    ) = None,
    model: str | None = None,
) -> CustomerIntelligenceCrewRunner:
    """Build one isolated Customer Intelligence runtime."""

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

    resolved_page_provider = (
        page_retrieval_provider
        if page_retrieval_provider is not None
        else FirecrawlPageRetrievalProvider()
    )

    resolved_model = (
        model
        if model is not None
        else settings.customer_intelligence_model
    )

    evidence_ledger = ResearchEvidenceLedger(
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE
    )

    tool_gateway = ToolGateway(
        web_search_provider=(
            resolved_search_provider
        ),
        page_retrieval_provider=(
            resolved_page_provider
        ),
    )

    search_tool = ControlledWebSearchTool(
        gateway=tool_gateway,
        stage=AnalysisStage.CUSTOMER_INTELLIGENCE,
        evidence_ledger=evidence_ledger,
        max_usage_count=3,
    )

    page_retrieval_tool = (
        ControlledBatchPageRetrievalTool(
            gateway=tool_gateway,
            stage=(
                AnalysisStage
                .CUSTOMER_INTELLIGENCE
            ),
            evidence_ledger=evidence_ledger,
            max_usage_count=2,
            max_workers=4,
        )
    )

    crewai_llm = CrewAILLMGatewayAdapter(
        gateway=resolved_llm_gateway,
        model=resolved_model,
    )

    return CustomerIntelligenceCrewRunner(
        llm=crewai_llm,
        search_tool=search_tool,
        page_retrieval_tool=(
            page_retrieval_tool
        ),
        evidence_ledger=evidence_ledger,
    )
