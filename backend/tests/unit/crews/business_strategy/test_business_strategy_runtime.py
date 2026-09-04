from unittest.mock import Mock

from app.crews.business_strategy.runtime import (
    build_business_strategy_runner,
)
from app.llm.gateway import (
    LLMGateway,
)


def test_runtime_wires_llm_gateway_and_model():
    llm_gateway = Mock(
        spec=LLMGateway
    )

    runner = (
        build_business_strategy_runner(
            llm_gateway=llm_gateway,
            model="test-strategy-model",
        )
    )

    crew = runner.build_crew()

    assert (
        crew.agents[0].llm.model
        == "test-strategy-model"
    )

    assert (
        crew.tasks[0].tools
        == []
    )