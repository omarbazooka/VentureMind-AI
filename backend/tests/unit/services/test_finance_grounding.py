from decimal import Decimal

import pytest

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
    EvidenceProvenance,
    MarketAnalysis,
    MarketFinding,
    MarketFindingCategory,
    ResearchClaimKind,
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchEvidenceSource,
    ResearchGateDecision,
    ResearchGateIssueCode,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import BusinessStrategyAnalysis
from app.services.finance_grounding import (
    FinanceGroundingError,
    finalize_financial_assumptions,
)


def make_strategy() -> BusinessStrategyAnalysis:
    return BusinessStrategyAnalysis(
        executive_summary="Bounded financial modeling is required.",
        finance_questions=[
            "What selling price should the venture use?"
        ],
    )


def make_assessment(
    *,
    stage: AnalysisStage,
    quality: ResearchEvidenceQuality,
) -> ResearchStageGateAssessment:
    insufficient = (
        quality == ResearchEvidenceQuality.INSUFFICIENT
    )
    return ResearchStageGateAssessment(
        stage=stage,
        attempt=1,
        stage_status=AnalysisStageStatus.COMPLETED,
        evidence_quality=quality,
        limitations=(
            ["Evidence is insufficient."]
            if insufficient
            else []
        ),
        retry_eligible=False,
        issue_codes=(
            [ResearchGateIssueCode.INSUFFICIENT_EVIDENCE]
            if insufficient
            else []
        ),
    )


def make_context(
    *,
    profile_data: dict | None = None,
    market_analysis: MarketAnalysis | None = None,
    market_insufficient: bool = True,
) -> FinanceAssumptionBuilderContext:
    market_quality = (
        ResearchEvidenceQuality.INSUFFICIENT
        if market_insufficient
        else ResearchEvidenceQuality.STRONG
    )

    assessments = [
        make_assessment(
            stage=AnalysisStage.MARKET_RESEARCH,
            quality=market_quality,
        ),
        make_assessment(
            stage=AnalysisStage.COMPETITOR_INTELLIGENCE,
            quality=ResearchEvidenceQuality.INSUFFICIENT,
        ),
        make_assessment(
            stage=AnalysisStage.CUSTOMER_INTELLIGENCE,
            quality=ResearchEvidenceQuality.INSUFFICIENT,
        ),
    ]

    insufficient_stages = [
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]
    if market_insufficient:
        insufficient_stages.insert(
            0,
            AnalysisStage.MARKET_RESEARCH,
        )

    gate = ResearchEvidenceGateResult(
        decision=ResearchGateDecision.INSUFFICIENT,
        can_proceed=True,
        assessments=assessments,
        retry_stages=[],
        insufficient_stages=insufficient_stages,
    )

    return FinanceAssumptionBuilderContext(
        profile_snapshot=AnalysisProfileSnapshot(
            readiness="READY_FOR_ANALYSIS",
            profile_data=(
                profile_data
                or {
                    "idea_description": "Gym management SaaS.",
                    "target_country": "Egypt",
                }
            ),
            profile_metadata={},
            unknown_fields=[],
        ),
        research_gate=gate,
        market_analysis=market_analysis,
        competitor_analysis=None,
        customer_analysis=None,
        business_strategy=make_strategy(),
    )


def make_market_analysis(
    *,
    value: str = "30",
    source_id: str = "market-cost-source",
) -> MarketAnalysis:
    return MarketAnalysis(
        summary="A numerical operating-cost benchmark was found.",
        findings=[
            MarketFinding(
                statement=(
                    "Observed operating cost benchmark is "
                    f"{value} EGP per customer."
                ),
                claim_kind=ResearchClaimKind.OBSERVED,
                confidence=0.9,
                evidence_source_ids=[source_id],
                is_numerical=True,
                category=MarketFindingCategory.OTHER,
            )
        ],
        evidence_sources=[
            ResearchEvidenceSource(
                source_id=source_id,
                provenance=EvidenceProvenance.WEB,
                title="Operating cost benchmark",
                url="https://example.com/cost-benchmark",
                excerpt=(
                    "Observed operating cost benchmark is "
                    f"{value} EGP per customer."
                ),
            )
        ],
        evidence_quality=ResearchEvidenceQuality.STRONG,
        limitations=[],
    )


def ai_draft(
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
        provenance=FinancialAssumptionProvenance.AI_ASSUMPTION,
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale="Explicit scenario assumption.",
    )


def user_draft(
    *,
    input_name: FinancialInputName,
    value: str,
    profile_field: str,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumptionDraft:
    return FinancialAssumptionDraft(
        input_name=input_name,
        value=Decimal(value),
        provenance=FinancialAssumptionProvenance.USER,
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale="User-provided financial value.",
        profile_fields=[profile_field],
    )


def web_variable_cost_draft(
    *,
    value: str = "30",
    source_id: str = "market-cost-source",
    stage: AnalysisStage = AnalysisStage.MARKET_RESEARCH,
) -> FinancialAssumptionDraft:
    return FinancialAssumptionDraft(
        input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
        value=Decimal(value),
        provenance=FinancialAssumptionProvenance.WEB,
        currency="EGP",
        unit_label="customer",
        rationale="Direct numerical research input.",
        supporting_stages=[stage],
        evidence_source_ids=[source_id],
    )


def make_scenario(
    *,
    scenario: FinancialScenarioKind,
    selling_price: FinancialAssumptionDraft | None = None,
    variable_cost: FinancialAssumptionDraft | None = None,
    starting_cash: FinancialAssumptionDraft | None = None,
) -> FinancialScenarioAssumptionDraft:
    return FinancialScenarioAssumptionDraft(
        scenario=scenario,
        selling_price_per_unit=(
            selling_price
            or ai_draft(
                input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
                value="250",
                currency="EGP",
                unit_label="customer",
            )
        ),
        sales_volume=ai_draft(
            input_name=FinancialInputName.SALES_VOLUME,
            value="100",
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=(
            variable_cost
            or ai_draft(
                input_name=FinancialInputName.VARIABLE_COST_PER_UNIT,
                value="50",
                currency="EGP",
                unit_label="customer",
            )
        ),
        fixed_costs=ai_draft(
            input_name=FinancialInputName.FIXED_COSTS,
            value="10000",
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        ),
        starting_cash=starting_cash,
    )


def make_bundle(
    *,
    base: FinancialScenarioAssumptionDraft | None = None,
    upside: FinancialScenarioAssumptionDraft | None = None,
    downside: FinancialScenarioAssumptionDraft | None = None,
) -> FinancialAssumptionDraftBundle:
    return FinancialAssumptionDraftBundle(
        base=(
            base
            or make_scenario(
                scenario=FinancialScenarioKind.BASE
            )
        ),
        upside=(
            upside
            or make_scenario(
                scenario=FinancialScenarioKind.UPSIDE
            )
        ),
        downside=(
            downside
            or make_scenario(
                scenario=FinancialScenarioKind.DOWNSIDE
            )
        ),
    )


def test_valid_user_value_is_grounded_from_profile():
    context = make_context(
        profile_data={
            "selling_price": "250 EGP per customer",
        }
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        selling_price=user_draft(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            value="250",
            profile_field="selling_price",
            currency="EGP",
            unit_label="customer",
        ),
    )

    result = finalize_financial_assumptions(
        drafts=make_bundle(base=base),
        context=context,
    )

    assert (
        result.base.selling_price_per_unit.provenance
        == FinancialAssumptionProvenance.USER
    )


def test_invented_profile_field_is_rejected():
    context = make_context(
        profile_data={
            "selling_price": "250 EGP per customer",
        }
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        selling_price=user_draft(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            value="250",
            profile_field="invented_price_field",
            currency="EGP",
            unit_label="customer",
        ),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=context,
        )


def test_user_value_not_present_in_profile_field_is_rejected():
    context = make_context(
        profile_data={
            "selling_price": "250 EGP per customer",
        }
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        selling_price=user_draft(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            value="300",
            profile_field="selling_price",
            currency="EGP",
            unit_label="customer",
        ),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=context,
        )


def test_valid_web_value_is_grounded_from_numerical_finding():
    market = make_market_analysis()
    context = make_context(
        market_analysis=market,
        market_insufficient=False,
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        variable_cost=web_variable_cost_draft(),
    )

    result = finalize_financial_assumptions(
        drafts=make_bundle(base=base),
        context=context,
    )

    assert (
        result.base.variable_cost_per_unit.provenance
        == FinancialAssumptionProvenance.WEB
    )


def test_invented_web_source_id_is_rejected():
    market = make_market_analysis()
    context = make_context(
        market_analysis=market,
        market_insufficient=False,
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        variable_cost=web_variable_cost_draft(
            source_id="invented-source"
        ),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=context,
        )


def test_web_value_without_numeric_support_is_rejected():
    market = make_market_analysis(value="30")
    context = make_context(
        market_analysis=market,
        market_insufficient=False,
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        variable_cost=web_variable_cost_draft(
            value="31"
        ),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=context,
        )


def test_web_value_from_insufficient_stage_is_rejected():
    context = make_context(
        market_analysis=None,
        market_insufficient=True,
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        variable_cost=web_variable_cost_draft(),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=context,
        )


def test_ai_assumptions_ground_without_external_lineage():
    result = finalize_financial_assumptions(
        drafts=make_bundle(),
        context=make_context(),
    )

    assert (
        result.base.sales_volume.provenance
        == FinancialAssumptionProvenance.AI_ASSUMPTION
    )


def test_unknown_critical_input_remains_unknown():
    unknown_price = FinancialAssumptionDraft(
        input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
        value=None,
        provenance=None,
        rationale="Selling price is unresolved.",
    )
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        selling_price=unknown_price,
    )

    result = finalize_financial_assumptions(
        drafts=make_bundle(base=base),
        context=make_context(),
    )

    assert result.base.selling_price_per_unit.value is None
    assert result.base.selling_price_per_unit.provenance is None


def test_ai_generated_starting_cash_is_rejected():
    base = make_scenario(
        scenario=FinancialScenarioKind.BASE,
        starting_cash=ai_draft(
            input_name=FinancialInputName.STARTING_CASH,
            value="100000",
            currency="EGP",
        ),
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(base=base),
            context=make_context(),
        )


def test_starting_cash_cannot_change_between_scenarios():
    context = make_context(
        profile_data={
            "starting_cash": [
                "100,000 EGP available",
                "200,000 EGP planned",
            ],
        }
    )
    base_cash = user_draft(
        input_name=FinancialInputName.STARTING_CASH,
        value="100000",
        profile_field="starting_cash",
        currency="EGP",
    )
    upside_cash = user_draft(
        input_name=FinancialInputName.STARTING_CASH,
        value="200000",
        profile_field="starting_cash",
        currency="EGP",
    )
    downside_cash = user_draft(
        input_name=FinancialInputName.STARTING_CASH,
        value="100000",
        profile_field="starting_cash",
        currency="EGP",
    )

    with pytest.raises(FinanceGroundingError):
        finalize_financial_assumptions(
            drafts=make_bundle(
                base=make_scenario(
                    scenario=FinancialScenarioKind.BASE,
                    starting_cash=base_cash,
                ),
                upside=make_scenario(
                    scenario=FinancialScenarioKind.UPSIDE,
                    starting_cash=upside_cash,
                ),
                downside=make_scenario(
                    scenario=FinancialScenarioKind.DOWNSIDE,
                    starting_cash=downside_cash,
                ),
            ),
            context=context,
        )
