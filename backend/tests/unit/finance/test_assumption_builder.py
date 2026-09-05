from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.finance.assumption_builder import (
    FinanceAssumptionBuilder,
    FinanceAssumptionBuilderError,
)
from app.llm.gateway import LLMGateway
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import (
    FinancialAssumptionProvenance,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
    FinancialAssumptionDraft,
    FinancialAssumptionDraftBundle,
    FinancialScenarioAssumptionDraft,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchGateIssueCode,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)

def make_context(
) -> FinanceAssumptionBuilderContext:
    research_stages = (
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage
        .COMPETITOR_INTELLIGENCE,
        AnalysisStage
        .CUSTOMER_INTELLIGENCE,
    )

    assessments = [
        ResearchStageGateAssessment(
            stage=stage,
            attempt=1,
            stage_status=(
                AnalysisStageStatus.COMPLETED
            ),
            evidence_quality=(
                ResearchEvidenceQuality
                .INSUFFICIENT
            ),
            limitations=[
                "Evidence is insufficient."
            ],
            retry_eligible=False,
            issue_codes=[
                ResearchGateIssueCode
                .INSUFFICIENT_EVIDENCE
            ],
        )
        for stage in research_stages
    ]

    gate = ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision
            .INSUFFICIENT
        ),
        can_proceed=True,
        assessments=assessments,
        retry_stages=[],
        insufficient_stages=list(
            research_stages
        ),
    )

    profile = AnalysisProfileSnapshot(
        readiness="READY_FOR_ANALYSIS",
        profile_data={
            "idea_description": (
                "Gym management SaaS."
            ),
            "target_country": "Egypt",
        },
        profile_metadata={},
        unknown_fields=[],
    )

    strategy = BusinessStrategyAnalysis(
        executive_summary=(
            "The venture needs bounded "
            "financial modeling."
        ),
        finance_questions=[
            (
                "What selling price should "
                "the venture use?"
            )
        ],
    )

    return FinanceAssumptionBuilderContext(
        profile_snapshot=profile,
        research_gate=gate,
        market_analysis=None,
        competitor_analysis=None,
        customer_analysis=None,
        business_strategy=strategy,
    )

def ai_assumption(
    *,
    input_name: FinancialInputName,
    value: str,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumptionDraft:
    return FinancialAssumptionDraft(
        input_name=input_name,
        value=Decimal(value),
        provenance=(
            FinancialAssumptionProvenance
            .AI_ASSUMPTION
        ),
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale=(
            "Explicit scenario assumption."
        ),
    )

def scenario_draft(
    scenario: FinancialScenarioKind,
) -> FinancialScenarioAssumptionDraft:
    return FinancialScenarioAssumptionDraft(
        scenario=scenario,

        selling_price_per_unit=(
            ai_assumption(
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                value="250",
                currency="EGP",
                unit_label="customer",
            )
        ),

        sales_volume=(
            ai_assumption(
                input_name=(
                    FinancialInputName
                    .SALES_VOLUME
                ),
                value="100",
                unit_label="customer",
                period=(
                    FinancialPeriod.MONTHLY
                ),
            )
        ),

        variable_cost_per_unit=(
            ai_assumption(
                input_name=(
                    FinancialInputName
                    .VARIABLE_COST_PER_UNIT
                ),
                value="50",
                currency="EGP",
                unit_label="customer",
            )
        ),

        fixed_costs=(
            ai_assumption(
                input_name=(
                    FinancialInputName
                    .FIXED_COSTS
                ),
                value="10000",
                currency="EGP",
                period=(
                    FinancialPeriod.MONTHLY
                ),
            )
        ),
    )

def test_builder_uses_structured_llm_output():
    expected = FinancialAssumptionDraftBundle(
        base=scenario_draft(
            FinancialScenarioKind.BASE
        ),
        upside=scenario_draft(
            FinancialScenarioKind.UPSIDE
        ),
        downside=scenario_draft(
            FinancialScenarioKind.DOWNSIDE
        ),
    )

    gateway = Mock(
        spec=LLMGateway
    )

    gateway.generate_structured.return_value = (
        expected
    )

    builder = FinanceAssumptionBuilder(
        llm_gateway=gateway,
        model="test-finance-model",
    )

    result = builder(
        make_context()
    )

    assert result == expected

    call = (
        gateway
        .generate_structured
        .call_args
        .kwargs
    )

    assert (
        call["model"]
        == "test-finance-model"
    )

    assert (
        call["response_model"]
        is FinancialAssumptionDraftBundle
    )

    assert (
        "Do not calculate revenue"
        in call["system_prompt"]
    )

    assert (
        "What selling price"
        in call["user_prompt"]
    )


def test_builder_is_single_use():
    expected = FinancialAssumptionDraftBundle(
        base=scenario_draft(
            FinancialScenarioKind.BASE
        ),
        upside=scenario_draft(
            FinancialScenarioKind.UPSIDE
        ),
        downside=scenario_draft(
            FinancialScenarioKind.DOWNSIDE
        ),
    )

    gateway = Mock(
        spec=LLMGateway
    )

    gateway.generate_structured.return_value = (
        expected
    )

    builder = FinanceAssumptionBuilder(
        llm_gateway=gateway,
        model="test-finance-model",
    )

    builder(
        make_context()
    )

    with pytest.raises(
        FinanceAssumptionBuilderError
    ):
        builder(
            make_context()
        )

    assert (
        gateway
        .generate_structured
        .call_count
        == 1
    )