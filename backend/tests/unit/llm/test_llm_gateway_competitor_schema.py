from unittest.mock import Mock

from app.llm.gateway import LLMGateway
from app.research.competitor_evidence import (
    CompetitorAnalysisDraft,
)


VALID_INSUFFICIENT_COMPETITOR_JSON = """
{
    "summary": "Evidence was insufficient.",
    "competitors": [],
    "findings": [],
    "evidence_quality": "INSUFFICIENT",
    "limitations": [
        "No reliable competitor evidence was available."
    ]
}
"""


def test_competitor_draft_schema_supports_nested_profiles():
    client = Mock()

    response = Mock()
    response.text = VALID_INSUFFICIENT_COMPETITOR_JSON

    client.models.generate_content.return_value = response

    gateway = LLMGateway(client=client)

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Synthesize competitor evidence.",
        user_prompt="Create CompetitorAnalysisDraft.",
        response_model=CompetitorAnalysisDraft,
    )

    call_kwargs = (
        client.models
        .generate_content
        .call_args
        .kwargs
    )

    schema = (
        call_kwargs["config"]
        ["response_json_schema"]
    )

    assert "CompetitorProfile" in schema["$defs"]
    assert "CompetitorDetail" in schema["$defs"]

    competitors_schema = (
        schema["properties"]["competitors"]
    )

    assert competitors_schema["type"] == "array"
    assert (
        competitors_schema["items"]["$ref"]
        == "#/$defs/CompetitorProfile"
    )

    assert isinstance(
        result,
        CompetitorAnalysisDraft,
    )
