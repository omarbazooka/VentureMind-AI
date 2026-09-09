from app.core.config import settings
from app.crews.validation.crew import ValidationCrewRunner
from app.llm.crewai_adapter import CrewAILLMGatewayAdapter
from app.llm.gateway import LLMGateway


def build_validation_runner(
    *,
    llm_gateway: LLMGateway | None = None,
    model: str | None = None,
) -> ValidationCrewRunner:
    resolved_llm_gateway = (
        llm_gateway if llm_gateway is not None else LLMGateway()
    )
    resolved_model = (
        model if model is not None else settings.risk_analysis_model
    )
    crewai_llm = CrewAILLMGatewayAdapter(
        gateway=resolved_llm_gateway,
        model=resolved_model,
    )
    return ValidationCrewRunner(llm=crewai_llm)
