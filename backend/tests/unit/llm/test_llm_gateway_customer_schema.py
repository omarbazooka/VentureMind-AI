from unittest.mock import Mock

from app.llm.gateway import LLMGateway
from app.research.customer_evidence import (
    CustomerAnalysisDraft,
)


VALID_INSUFFICIENT_CUSTOMER_JSON = """
{
    "summary": "Evidence was insufficient.",
    "findings": [],
    "evidence_quality": "INSUFFICIENT",
    "limitations": [
        "No reliable target customer evidence was available."
    ]
}
"""


def test_customer_draft_schema_supports_customer_findings():
    client = Mock()

    response = Mock()
    response.text = VALID_INSUFFICIENT_CUSTOMER_JSON

    client.models.generate_content.return_value = response

    gateway = LLMGateway(client=client)

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Synthesize customer evidence.",
        user_prompt="Create CustomerAnalysisDraft.",
        response_model=CustomerAnalysisDraft,
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

    assert "CustomerFinding" in schema["$defs"]
    assert "CustomerFindingCategory" in schema["$defs"]

    findings_schema = (
        schema["properties"]["findings"]
    )

    assert findings_schema["type"] == "array"
    assert (
        findings_schema["items"]["$ref"]
        == "#/$defs/CustomerFinding"
    )

    assert isinstance(
        result,
        CustomerAnalysisDraft,
    )
