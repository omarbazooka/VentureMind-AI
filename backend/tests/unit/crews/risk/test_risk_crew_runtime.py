from unittest.mock import Mock

from app.crews.risk.runtime import build_risk_runner
from app.llm.gateway import LLMGateway


def test_runtime_wires_llm_gateway_and_model():
    llm_gateway = Mock(spec=LLMGateway)
    runner = build_risk_runner(
        llm_gateway=llm_gateway,
        model="test-risk-model",
    )
    crew = runner.build_crew()

    assert crew.agents[0].llm.model == "test-risk-model"
    assert crew.tasks[0].tools == []
