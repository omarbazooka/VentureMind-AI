from unittest.mock import Mock

from app.llm.gateway import LLMGateway
from app.schemas.research import MarketAnalysis


VALID_INSUFFICIENT_MARKET_JSON = """
{
    "summary": "Evidence was insufficient.",
    "findings": [],
    "evidence_sources": [],
    "evidence_quality": "INSUFFICIENT",
    "limitations": [
        "No reliable market evidence was available."
    ]
}
"""


def test_market_schema_removes_unsupported_uri_format():
    client = Mock()

    response = Mock()
    response.text = VALID_INSUFFICIENT_MARKET_JSON

    client.models.generate_content.return_value = (
        response
    )

    gateway = LLMGateway(
        client=client
    )

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Synthesize market evidence.",
        user_prompt="Create MarketAnalysis.",
        response_model=MarketAnalysis,
    )

    call_kwargs = (
        client.models
        .generate_content
        .call_args
        .kwargs
    )

    schema = (
        call_kwargs["config"][
            "response_json_schema"
        ]
    )

    evidence_source_schema = (
        schema["$defs"][
            "ResearchEvidenceSource"
        ]["properties"]
    )

    url_string_schema = (
        evidence_source_schema[
            "url"
        ]["anyOf"][0]
    )

    retrieved_at_string_schema = (
        evidence_source_schema[
            "retrieved_at"
        ]["anyOf"][0]
    )

    assert (
        "format"
        not in url_string_schema
    )

    assert (
        retrieved_at_string_schema[
            "format"
        ]
        == "date-time"
    )

    assert isinstance(
        result,
        MarketAnalysis,
    )
