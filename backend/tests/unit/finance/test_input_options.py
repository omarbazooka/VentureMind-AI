from decimal import Decimal

from app.finance.input_options import (
    build_finance_input_request,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
)
from app.schemas.finance_runtime import (
    FinanceInputOptionBasis,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CompetitorDetail,
    CompetitorProfile,
    CompetitorRelationship,
    EvidenceProvenance,
    ResearchClaimKind,
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)


def _gate() -> ResearchEvidenceGateResult:
    assessments = [
        ResearchStageGateAssessment(
            stage=AnalysisStage.MARKET_RESEARCH,
            attempt=1,
            stage_status=AnalysisStageStatus.COMPLETED,
            evidence_quality=(
                ResearchEvidenceQuality.INSUFFICIENT
            ),
        ),
        ResearchStageGateAssessment(
            stage=(
                AnalysisStage
                .COMPETITOR_INTELLIGENCE
            ),
            attempt=1,
            stage_status=AnalysisStageStatus.COMPLETED,
            evidence_quality=ResearchEvidenceQuality.STRONG,
        ),
        ResearchStageGateAssessment(
            stage=AnalysisStage.CUSTOMER_INTELLIGENCE,
            attempt=1,
            stage_status=AnalysisStageStatus.COMPLETED,
            evidence_quality=(
                ResearchEvidenceQuality.INSUFFICIENT
            ),
        ),
    ]

    return ResearchEvidenceGateResult(
        decision=ResearchGateDecision.INSUFFICIENT,
        can_proceed=True,
        assessments=assessments,
        insufficient_stages=[
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage.CUSTOMER_INTELLIGENCE,
        ],
    )


def _competitor(
    *,
    name: str,
    price: str,
    source_id: str,
) -> CompetitorProfile:
    return CompetitorProfile(
        name=name,
        relationship=CompetitorRelationship.DIRECT,
        relevance_summary="Direct comparable competitor.",
        confidence=0.9,
        primary_source_id=source_id,
        pricing=CompetitorDetail(
            statement=(
                f"{price} EGP per customer"
            ),
            claim_kind=ResearchClaimKind.OBSERVED,
            confidence=0.9,
            evidence_source_ids=[source_id],
            is_numerical=True,
        ),
    )


def _context() -> FinanceAssumptionBuilderContext:
    analysis = CompetitorAnalysis(
        summary="Observed competitor pricing.",
        competitors=[
            _competitor(
                name="Competitor A",
                price="200",
                source_id="source-a",
            ),
            _competitor(
                name="Competitor B",
                price="400",
                source_id="source-b",
            ),
        ],
        evidence_sources=[
            ResearchEvidenceSource(
                source_id="source-a",
                provenance=EvidenceProvenance.WEB,
                title="Competitor A pricing",
                url="https://example.com/a",
            ),
            ResearchEvidenceSource(
                source_id="source-b",
                provenance=EvidenceProvenance.WEB,
                title="Competitor B pricing",
                url="https://example.com/b",
            ),
        ],
        evidence_quality=ResearchEvidenceQuality.STRONG,
    )

    return FinanceAssumptionBuilderContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness=(
                ProfileReadinessStatus.READY_FOR_ANALYSIS
            ),
            profile_data={
                "idea_description": "Test SaaS",
                "target_country": "Egypt",
            },
        ),
        research_gate=_gate(),
        competitor_analysis=analysis,
        business_strategy=BusinessStrategyAnalysis(
            executive_summary="Proceed cautiously.",
            finance_questions=[
                "Which selling price should be modeled?"
            ],
        ),
    )


def _assumption(
    *,
    input_name: FinancialInputName,
    value: Decimal | None,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        value=value,
        provenance=(
            FinancialAssumptionProvenance.AI_ASSUMPTION
            if value is not None
            else None
        ),
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale="Test assumption.",
    )


def _assumptions(
    *,
    unit_label: str = "customer",
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=FinancialScenarioKind.BASE,
        selling_price_per_unit=_assumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=None,
            currency="EGP",
            unit_label=unit_label,
        ),
        sales_volume=_assumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=Decimal("100"),
            unit_label=unit_label,
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_assumption(
            input_name=(
                FinancialInputName
                .VARIABLE_COST_PER_UNIT
            ),
            value=Decimal("50"),
            currency="EGP",
            unit_label=unit_label,
        ),
        fixed_costs=_assumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=Decimal("10000"),
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        ),
    )


def test_selling_price_request_builds_low_mid_high_market_options():
    request = build_finance_input_request(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        assumptions=_assumptions(),
        context=_context(),
    )

    assert [
        option.option_id
        for option in request.options
    ] == [
        "market_low",
        "market_midpoint",
        "market_high",
    ]
    assert [
        option.value
        for option in request.options
    ] == [
        Decimal("200"),
        Decimal("300"),
        Decimal("400"),
    ]
    assert (
        request.options[1].basis
        == FinanceInputOptionBasis.CALCULATED_FROM_WEB
    )
    assert request.allow_custom is True


def test_market_options_are_not_built_for_incompatible_unit_basis():
    request = build_finance_input_request(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        assumptions=_assumptions(
            unit_label="seat"
        ),
        context=_context(),
    )

    assert request.options == []
    assert request.unit_label == "seat"


def test_non_price_missing_input_uses_direct_question_without_options():
    request = build_finance_input_request(
        input_name=FinancialInputName.SALES_VOLUME,
        assumptions=_assumptions(),
        context=_context(),
    )

    assert request.options == []
    assert request.period == FinancialPeriod.MONTHLY
    assert request.unit_label == "customer"
