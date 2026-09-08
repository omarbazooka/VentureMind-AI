from app.core.config import settings
from app.crews.risk.crew import RiskCrewRunner
from app.llm.crewai_adapter import CrewAILLMGatewayAdapter
from app.llm.gateway import LLMGateway


def build_risk_runner(
    *,
    llm_gateway: LLMGateway | None = None,
    model: str | None = None,
) -> RiskCrewRunner:
    resolved_llm_gateway = (
        llm_gateway
        if llm_gateway is not None
        else LLMGateway()
    )
    resolved_model = (
        model
        if model is not None
        else settings.risk_analysis_model
    )
    crewai_llm = CrewAILLMGatewayAdapter(
        gateway=resolved_llm_gateway,
        model=resolved_model,
    )
    return RiskCrewRunner(llm=crewai_llm)
