from app.core.config import settings
from app.crews.business_strategy.crew import (
    BusinessStrategyCrewRunner,
)
from app.llm.crewai_adapter import (
    CrewAILLMGatewayAdapter,
)
from app.llm.gateway import (
    LLMGateway,
)


def build_business_strategy_runner(
    *,
    llm_gateway : LLMGateway | None = None,
    model: str | None = None,
) -> BusinessStrategyCrewRunner:
    """
    Build one isolated Business Strategy
    stage runtime.
    """

    resolved_llm_gateway = (
        llm_gateway 
        if llm_gateway is not None
        else LLMGateway()
    )

    resolved_model = (
        model
        if model is not None
        else settings.business_strategy_model
    )
    
    crewai_llm = (
        CrewAILLMGatewayAdapter(
            gateway=resolved_llm_gateway,
            model=resolved_model,
        )
    )

    return BusinessStrategyCrewRunner(
        llm=crewai_llm,
    )