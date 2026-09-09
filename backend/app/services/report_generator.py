from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.idea import Idea
from app.models.report import Report
from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.decision import FinalDecisionAnalysis
from app.schemas.finance import (
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioKind,
)
from app.schemas.report import (
    ReportAnalyticsSection,
    ReportChartData,
    ReportCompetitorSection,
    ReportCustomerSection,
    ReportFinanceSection,
    ReportMarketMetrics,
    ReportMarketSection,
    ReportMetricStatus,
    ReportMetricValue,
    ReportRiskSection,
    ReportSourceItem,
    ReportStrategySection,
    ReportValidationSection,
    StructuredReport,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
)
from app.schemas.risk import RiskAnalysis
from app.schemas.strategy import BusinessStrategyAnalysis
from app.schemas.validation import ValidationAnalysis


class ReportGenerationError(RuntimeError):
    pass


def _extract_metric_value(
    metrics: list[Any], metric_name: FinancialMetricName
) -> Decimal | None:
    for m in metrics:
        name = m.metric_name if hasattr(m, "metric_name") else m.get("metric_name")
        val = m.value if hasattr(m, "value") else m.get("value")
        if name == metric_name or name == metric_name.value:
            if val is not None:
                return Decimal(str(val))
    return None


def _build_chart_data(
    finance_bundle: FinancialScenarioBundle,
    analytics_result: DecisionAnalyticsResult,
    risk_analysis: RiskAnalysis,
) -> ReportChartData:
    break_even_comparison: list[dict[str, Any]] = []
    monthly_projections: list[dict[str, Any]] = []
    sensitivity_ranking: list[dict[str, Any]] = []
    risk_matrix: list[dict[str, Any]] = []

    # Break-even comparison
    for sc_name, sc_data in (
        ("BASE", finance_bundle.base),
        ("UPSIDE", finance_bundle.upside),
        ("DOWNSIDE", finance_bundle.downside),
    ):
        sc_dict = sc_data.model_dump(mode="json")
        metrics = sc_dict.get("metrics", [])
        be_units = _extract_metric_value(
            metrics, FinancialMetricName.BREAK_EVEN_UNITS
        )
        currency = None
        for m in metrics:
            if m.get("currency"):
                currency = m["currency"]
                break

        price_val = sc_dict.get("assumptions", {}).get(
            "selling_price_per_unit", {}
        ).get("value")
        be_rev = (
            float(be_units) * float(price_val)
            if (be_units is not None and price_val is not None)
            else None
        )

        break_even_comparison.append(
            {
                "scenario": sc_name,
                "break_even_units": float(be_units) if be_units is not None else None,
                "break_even_revenue": be_rev,
                "currency": currency,
            }
        )

    # Monthly projections for base scenario (12 months)
    base_dict = finance_bundle.base.model_dump(mode="json")
    base_metrics = base_dict.get("metrics", [])
    base_assumptions = base_dict.get("assumptions", {})

    rev_metric = _extract_metric_value(
        base_metrics, FinancialMetricName.REVENUE
    )
    var_cost_metric = _extract_metric_value(
        base_metrics, FinancialMetricName.VARIABLE_COSTS
    )
    fixed_cost_val = base_assumptions.get("fixed_costs", {}).get("value")
    cost_metric = (
        (var_cost_metric or Decimal("0"))
        + (Decimal(str(fixed_cost_val)) if fixed_cost_val is not None else Decimal("0"))
    )
    op_profit_metric = _extract_metric_value(
        base_metrics, FinancialMetricName.OPERATING_RESULT
    )

    monthly_rev = float(rev_metric) if rev_metric is not None else 0.0
    monthly_cost = float(cost_metric) if cost_metric is not None else 0.0
    monthly_profit = float(op_profit_metric) if op_profit_metric is not None else 0.0

    # If assumption volume/fixed cost was annual, normalize to monthly
    vol_period = base_assumptions.get("sales_volume", {}).get("period")
    if vol_period == FinancialPeriod.ANNUAL.value:
        monthly_rev = round(monthly_rev / 12, 2)
        monthly_cost = round(monthly_cost / 12, 2)
        monthly_profit = round(monthly_profit / 12, 2)

    cumulative_cash = 0.0
    starting_cash_obj = base_assumptions.get("starting_cash")
    starting_cash_val = (
        starting_cash_obj.get("value")
        if isinstance(starting_cash_obj, dict)
        else None
    )
    if starting_cash_val is not None:
        cumulative_cash = float(starting_cash_val)

    for m in range(1, 13):
        # Apply modest initial ramp for months 1-3
        ramp = min(1.0, 0.4 + (m * 0.2)) if m <= 3 else 1.0
        m_rev = round(monthly_rev * ramp, 2)
        m_cost = round(monthly_cost * (0.8 if m <= 2 else 1.0), 2)
        m_profit = round(m_rev - m_cost, 2)
        cumulative_cash = round(cumulative_cash + m_profit, 2)

        monthly_projections.append(
            {
                "month": m,
                "revenue": m_rev,
                "costs": m_cost,
                "profit": m_profit,
                "cumulative_cash": cumulative_cash,
            }
        )

    # Sensitivity ranking
    if analytics_result.sensitivity is not None:
        for inp in analytics_result.sensitivity.inputs:
            item_name = inp.input_name.value
            shock_pct = float(analytics_result.sensitivity.shock_percent)
            impacts_list = []
            for imp in inp.increase.impacts:
                impacts_list.append(
                    {
                        "metric_name": imp.metric_name.value,
                        "change_percent": (
                            float(imp.output_relative_change_percent)
                            if imp.output_relative_change_percent is not None
                            else None
                        ),
                    }
                )
            sensitivity_ranking.append(
                {
                    "input_name": item_name,
                    "shock_percent": shock_pct,
                    "impacts": impacts_list,
                }
            )

    # Risk matrix
    for r in risk_analysis.risks:
        risk_matrix.append(
            {
                "category": r.category.value,
                "title": r.title,
                "likelihood": r.likelihood.value,
                "impact": r.impact.value,
                "score": r.risk_score,
                "level": r.risk_level.value,
                "mitigation_actions": r.mitigation_actions,
            }
        )

    return ReportChartData(
        break_even_comparison=break_even_comparison,
        monthly_projections=monthly_projections,
        sensitivity_ranking=sensitivity_ranking,
        risk_matrix=risk_matrix,
    )


def generate_structured_report(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> tuple[Report, StructuredReport]:
    run = db.get(AnalysisRun, analysis_run_id)
    if run is None:
        raise ReportGenerationError(
            f"AnalysisRun with ID {analysis_run_id} not found"
        )

    idea = db.get(Idea, run.idea_id)
    if idea is None:
        raise ReportGenerationError(f"Idea with ID {run.idea_id} not found")

    # Load all results
    results = db.scalars(
        select(AnalysisResult).where(
            AnalysisResult.analysis_run_id == analysis_run_id
        )
    ).all()
    results_by_stage: dict[str, AnalysisResult] = {
        res.stage: res for res in results
    }

    # Ensure required stages are available
    required_stages = [
        AnalysisStage.MARKET_RESEARCH.value,
        AnalysisStage.COMPETITOR_INTELLIGENCE.value,
        AnalysisStage.CUSTOMER_INTELLIGENCE.value,
        AnalysisStage.BUSINESS_STRATEGY.value,
        AnalysisStage.FINANCE.value,
        AnalysisStage.DECISION_ANALYTICS.value,
        AnalysisStage.RISK.value,
        AnalysisStage.INDEPENDENT_VALIDATION.value,
        AnalysisStage.INVESTMENT_COMMITTEE.value,
    ]
    missing = [s for s in required_stages if s not in results_by_stage]
    if missing:
        raise ReportGenerationError(
            f"Cannot generate report: missing stage results for {missing}"
        )

    # Parse stage analyses
    mkt_raw = results_by_stage[AnalysisStage.MARKET_RESEARCH.value].result_data
    comp_raw = results_by_stage[
        AnalysisStage.COMPETITOR_INTELLIGENCE.value
    ].result_data
    cust_raw = results_by_stage[
        AnalysisStage.CUSTOMER_INTELLIGENCE.value
    ].result_data
    strat_raw = results_by_stage[
        AnalysisStage.BUSINESS_STRATEGY.value
    ].result_data
    fin_raw = results_by_stage[AnalysisStage.FINANCE.value].result_data
    da_raw = results_by_stage[
        AnalysisStage.DECISION_ANALYTICS.value
    ].result_data
    risk_raw = results_by_stage[AnalysisStage.RISK.value].result_data
    val_raw = results_by_stage[
        AnalysisStage.INDEPENDENT_VALIDATION.value
    ].result_data
    dec_raw = results_by_stage[
        AnalysisStage.INVESTMENT_COMMITTEE.value
    ].result_data

    mkt_model = MarketAnalysis.model_validate(mkt_raw)
    comp_model = CompetitorAnalysis.model_validate(comp_raw)
    cust_model = CustomerAnalysis.model_validate(cust_raw)
    strat_model = BusinessStrategyAnalysis.model_validate(strat_raw)
    fin_model = FinancialScenarioBundle.model_validate(fin_raw)
    da_model = DecisionAnalyticsResult.model_validate(da_raw)
    risk_model = RiskAnalysis.model_validate(risk_raw)
    val_model = ValidationAnalysis.model_validate(val_raw)
    dec_model = FinalDecisionAnalysis.model_validate(dec_raw)

    # Collect all sources
    sources: list[ReportSourceItem] = []
    seen_source_ids: set[str] = set()

    for s in mkt_model.evidence_sources:
        if s.source_id not in seen_source_ids:
            seen_source_ids.add(s.source_id)
            sources.append(
                ReportSourceItem(
                    source_id=s.source_id,
                    title=s.title,
                    url=str(s.url) if s.url else None,
                    provenance=s.provenance.value,
                    stage=AnalysisStage.MARKET_RESEARCH.value,
                )
            )

    for s in comp_model.evidence_sources:
        if s.source_id not in seen_source_ids:
            seen_source_ids.add(s.source_id)
            sources.append(
                ReportSourceItem(
                    source_id=s.source_id,
                    title=s.title,
                    url=str(s.url) if s.url else None,
                    provenance=s.provenance.value,
                    stage=AnalysisStage.COMPETITOR_INTELLIGENCE.value,
                )
            )

    for s in cust_model.evidence_sources:
        if s.source_id not in seen_source_ids:
            seen_source_ids.add(s.source_id)
            sources.append(
                ReportSourceItem(
                    source_id=s.source_id,
                    title=s.title,
                    url=str(s.url) if s.url else None,
                    provenance=s.provenance.value,
                    stage=AnalysisStage.CUSTOMER_INTELLIGENCE.value,
                )
            )

    # Build sections
    market_section = ReportMarketSection(
        summary=mkt_model.summary,
        evidence_quality=mkt_model.evidence_quality.value,
        findings=[f.model_dump(mode="json") for f in mkt_model.findings],
        market_metrics=ReportMarketMetrics(),  # Allow unavailable states per Correction 3
        limitations=mkt_model.limitations,
    )

    competitor_section = ReportCompetitorSection(
        summary=comp_model.summary,
        evidence_quality=comp_model.evidence_quality.value,
        competitors=[
            c.model_dump(mode="json") for c in comp_model.competitors
        ],
        findings=[f.model_dump(mode="json") for f in comp_model.findings],
        limitations=comp_model.limitations,
    )

    customer_section = ReportCustomerSection(
        summary=cust_model.summary,
        evidence_quality=cust_model.evidence_quality.value,
        findings=[f.model_dump(mode="json") for f in cust_model.findings],
        limitations=cust_model.limitations,
    )

    strategy_section = ReportStrategySection(
        executive_summary=strat_model.executive_summary,
        positioning=[
            p.model_dump(mode="json") for p in strat_model.positioning
        ],
        value_proposition=[
            v.model_dump(mode="json") for v in strat_model.value_proposition
        ],
        business_model_implications=[
            b.model_dump(mode="json")
            for b in strat_model.business_model_implications
        ],
        go_to_market=[
            g.model_dump(mode="json") for g in strat_model.go_to_market
        ],
        strategic_strengths=[
            s.model_dump(mode="json")
            for s in strat_model.strategic_strengths
        ],
        strategic_weaknesses=[
            w.model_dump(mode="json")
            for w in strat_model.strategic_weaknesses
        ],
        critical_assumptions=[
            c.model_dump(mode="json")
            for c in strat_model.critical_assumptions
        ],
        limitations=strat_model.limitations,
    )

    finance_section = ReportFinanceSection(
        executive_summary=(
            f"Financial analysis evaluated Base, Upside, and Downside scenarios. "
            f"Base monthly revenue is estimated at "
            f"{_extract_metric_value(fin_model.base.metrics, FinancialMetricName.REVENUE) or 'N/A'}, "
            f"with operating profit of "
            f"{_extract_metric_value(fin_model.base.metrics, FinancialMetricName.OPERATING_RESULT) or 'N/A'}."
        ),
        base_scenario=fin_model.base.model_dump(mode="json"),
        upside_scenario=fin_model.upside.model_dump(mode="json"),
        downside_scenario=fin_model.downside.model_dump(mode="json"),
        comparisons=[
            c.model_dump(mode="json") for c in fin_model.comparisons
        ],
        limitations=fin_model.limitations,
    )

    analytics_section = ReportAnalyticsSection(
        kpis=[k.model_dump(mode="json") for k in da_model.kpis],
        scenario_relative_changes=[
            s.model_dump(mode="json")
            for s in da_model.scenario_relative_changes
        ],
        sensitivity=(
            da_model.sensitivity.model_dump(mode="json")
            if da_model.sensitivity
            else None
        ),
        limitations=da_model.limitations,
    )

    risk_section = ReportRiskSection(
        executive_summary=risk_model.executive_summary,
        overall_level=(
            risk_model.overall_level.value
            if risk_model.overall_level
            else None
        ),
        risks=[r.model_dump(mode="json") for r in risk_model.risks],
        limitations=risk_model.limitations,
    )

    validation_section = ReportValidationSection(
        status=val_model.status.value,
        executive_assessment=val_model.executive_assessment,
        issues=[i.model_dump(mode="json") for i in val_model.issues],
        limitations=val_model.limitations,
    )

    chart_data = _build_chart_data(
        finance_bundle=fin_model,
        analytics_result=da_model,
        risk_analysis=risk_model,
    )

    # Determine version
    latest_version = db.scalar(
        select(Report.version)
        .where(Report.idea_id == run.idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    report_version = (latest_version or 0) + 1

    report_id = uuid4()
    now = datetime.now(timezone.utc)

    structured_report = StructuredReport(
        id=report_id,
        idea_id=run.idea_id,
        analysis_run_id=analysis_run_id,
        version=report_version,
        title=f"VentureMind Evaluation: {idea.title}",
        executive_summary=dec_model.rationale,
        decision=dec_model,
        profile_summary=run.profile_snapshot.get("profile_data", {}),
        market=market_section,
        competitors=competitor_section,
        customer=customer_section,
        strategy=strategy_section,
        finance=finance_section,
        analytics=analytics_section,
        risk=risk_section,
        validation=validation_section,
        chart_data=chart_data,
        sources=sources,
        created_at=now,
    )

    persisted_report = Report(
        id=report_id,
        idea_id=run.idea_id,
        analysis_run_id=analysis_run_id,
        version=report_version,
        report_data=structured_report.model_dump(mode="json"),
        created_at=now,
    )
    db.add(persisted_report)
    db.flush()

    return persisted_report, structured_report
