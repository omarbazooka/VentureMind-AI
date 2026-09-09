from decimal import Decimal, InvalidOperation
from typing import Any

from app.schemas.report import StructuredReport
from app.schemas.report_action import (
    ReportActionRequest,
    ReportActionResponse,
    ReportActionType,
)


def _lines(values: list[str], *, empty_message: str) -> str:
    cleaned = [value.strip() for value in values if value and value.strip()]
    if not cleaned:
        return f"- {empty_message}"
    return "\n".join(f"- {value}" for value in cleaned)


def _report_ref(path: str) -> str:
    return f"REPORT:{path}"


def _source_ids_for_section(report: StructuredReport, section: str) -> list[str]:
    stage_by_section = {
        "market": "MARKET_RESEARCH",
        "competitor": "COMPETITOR_INTELLIGENCE",
        "competitors": "COMPETITOR_INTELLIGENCE",
        "customer": "CUSTOMER_INTELLIGENCE",
        "customers": "CUSTOMER_INTELLIGENCE",
    }
    stage = stage_by_section.get(section)
    if stage is None:
        return []
    return [source.source_id for source in report.sources if source.stage == stage]


def _extract_assumption_value(base: dict[str, Any], name: str) -> tuple[Any, str | None]:
    assumption = base.get("assumptions", {}).get(name, {})
    if not isinstance(assumption, dict):
        return None, None
    return assumption.get("value"), assumption.get("currency")


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _break_even_action(
    *, report: StructuredReport, action: ReportActionType
) -> ReportActionResponse:
    base = report.finance.base_scenario
    price_raw, price_currency = _extract_assumption_value(
        base, "selling_price_per_unit"
    )
    variable_raw, variable_currency = _extract_assumption_value(
        base, "variable_cost_per_unit"
    )
    fixed_raw, fixed_currency = _extract_assumption_value(
        base, "fixed_costs"
    )
    price = _safe_decimal(price_raw)
    variable = _safe_decimal(variable_raw)
    fixed = _safe_decimal(fixed_raw)

    base_break_even = next(
        (
            item
            for item in report.chart_data.break_even_comparison
            if item.get("scenario") == "BASE"
        ),
        None,
    )

    if (
        price is None
        or variable is None
        or fixed is None
        or base_break_even is None
        or base_break_even.get("break_even_units") is None
    ):
        return ReportActionResponse(
            action=action,
            title="Break-Even Calculation",
            content=(
                "The persisted report does not contain enough authoritative "
                "Finance inputs to explain the break-even calculation."
            ),
            grounding_references=[_report_ref("finance.base_scenario")],
            metadata={"available": False},
        )

    currency = price_currency or variable_currency or fixed_currency
    contribution_margin = price - variable
    break_even_units = base_break_even.get("break_even_units")
    break_even_revenue = base_break_even.get("break_even_revenue")
    period = base_break_even.get("period")

    content = (
        "### Break-Even Calculation\n\n"
        "**Formula**\n\n"
        "Break-even units = Fixed costs / (Selling price per unit - Variable cost per unit)\n\n"
        "**Persisted Base inputs**\n"
        f"- Selling price per unit: {price}"
        + (f" {currency}" if currency else "")
        + "\n"
        f"- Variable cost per unit: {variable}"
        + (f" {currency}" if currency else "")
        + "\n"
        f"- Contribution margin per unit: {contribution_margin}"
        + (f" {currency}" if currency else "")
        + "\n"
        f"- Fixed costs: {fixed}"
        + (f" {currency}" if currency else "")
        + (f" / {period.lower()}" if isinstance(period, str) else "")
        + "\n\n"
        f"**Authoritative break-even units:** {break_even_units}"
    )
    if break_even_revenue is not None:
        content += (
            "\n**Derived break-even revenue:** "
            f"{break_even_revenue}"
            + (f" {currency}" if currency else "")
        )

    return ReportActionResponse(
        action=action,
        title="Break-Even Calculation",
        content=content,
        grounding_references=[
            _report_ref("finance.base_scenario.assumptions"),
            _report_ref("chart_data.break_even_comparison.BASE"),
        ],
        metadata={
            "available": True,
            "break_even_units": break_even_units,
            "break_even_revenue": break_even_revenue,
        },
    )


def _show_sources(
    *, report: StructuredReport, action: ReportActionType
) -> ReportActionResponse:
    if not report.sources:
        return ReportActionResponse(
            action=action,
            title="Report Evidence Sources",
            content="No persisted WEB evidence sources are available for this report.",
            grounding_references=[],
            metadata={"source_count": 0},
        )

    content = "### Persisted Evidence Sources\n\n" + "\n".join(
        (
            f"- **{source.title}** — {source.provenance} — {source.stage}"
            + (f" — {source.url}" if source.url else "")
        )
        for source in report.sources
    )
    return ReportActionResponse(
        action=action,
        title="Report Evidence Sources",
        content=content,
        grounding_references=[source.source_id for source in report.sources],
        metadata={"source_count": len(report.sources)},
    )


def _show_evidence(
    *, report: StructuredReport, request: ReportActionRequest
) -> ReportActionResponse:
    section = (request.target_section or "").strip().lower()

    if section == "market":
        findings = report.market.findings
        quality = report.market.evidence_quality
        limitations = report.market.limitations
    elif section in {"competitor", "competitors"}:
        findings = report.competitors.findings
        quality = report.competitors.evidence_quality
        limitations = report.competitors.limitations
    elif section in {"customer", "customers"}:
        findings = report.customer.findings
        quality = report.customer.evidence_quality
        limitations = report.customer.limitations
    else:
        return ReportActionResponse(
            action=request.action,
            title="Evidence",
            content=(
                "Select Market, Competitors, or Customers to inspect the persisted "
                "research evidence for that section."
            ),
            grounding_references=[],
            metadata={"available": False},
        )

    finding_lines = [str(item) for item in findings]
    source_ids = _source_ids_for_section(report, section)
    content = (
        f"### {section.title()} Evidence\n\n"
        f"**Evidence quality:** {quality}\n\n"
        "**Persisted findings**\n"
        + _lines(
            finding_lines,
            empty_message="No structured findings are persisted for this section.",
        )
        + "\n\n**Limitations**\n"
        + _lines(
            limitations,
            empty_message="No additional limitations are recorded for this section.",
        )
    )
    if not source_ids:
        content += "\n\nNo persisted WEB source IDs are attached to this section."

    return ReportActionResponse(
        action=request.action,
        title=f"Evidence for {section.title()}",
        content=content,
        grounding_references=source_ids,
        metadata={"source_count": len(source_ids)},
    )


def _challenge_conclusion(
    *, report: StructuredReport, action: ReportActionType
) -> ReportActionResponse:
    decision = report.decision
    content = (
        "### Challenge the Current Conclusion\n\n"
        f"**Current recommendation:** {decision.decision.value}\n"
        f"**Confidence:** {decision.confidence.value}\n\n"
        "**Recorded negative signals**\n"
        + _lines(
            decision.strongest_negative_signals,
            empty_message="No negative signals are recorded in the persisted Final Decision.",
        )
        + "\n\n**Critical assumptions**\n"
        + _lines(
            decision.critical_assumptions,
            empty_message="No critical assumptions are recorded in the persisted Final Decision.",
        )
        + "\n\n**What could change the decision**\n"
        + _lines(
            decision.what_could_change,
            empty_message="No decision-flip conditions are recorded in the persisted Final Decision.",
        )
        + "\n\n**Known limitations**\n"
        + _lines(
            decision.limitations,
            empty_message="No additional limitations are recorded in the persisted Final Decision.",
        )
    )
    return ReportActionResponse(
        action=action,
        title="Conclusion Challenge",
        content=content,
        grounding_references=[
            _report_ref("decision.strongest_negative_signals"),
            _report_ref("decision.critical_assumptions"),
            _report_ref("decision.what_could_change"),
            _report_ref("decision.limitations"),
        ],
    )


def _explain_chart(
    *, report: StructuredReport, request: ReportActionRequest
) -> ReportActionResponse:
    metric = (request.target_metric or "").strip().lower()
    if "monthly" in metric or "projection" in metric:
        if not report.chart_data.monthly_projections:
            return ReportActionResponse(
                action=request.action,
                title="Monthly Projection",
                content=(
                    "No authoritative month-by-month projection series is available. "
                    "VentureMind will not invent a monthly ramp in the report layer."
                ),
                grounding_references=[_report_ref("chart_data.monthly_projections")],
                metadata={"available": False},
            )

    if "break_even" in metric or "breakeven" in metric:
        if not report.chart_data.break_even_comparison:
            content = "No authoritative break-even chart data is available in this report."
        else:
            content = (
                "The break-even comparison uses the persisted Finance scenario results. "
                "Each point shows the calculated break-even units for Base, Upside, "
                "and Downside; break-even revenue is derived only when both break-even "
                "units and selling price are available."
            )
        return ReportActionResponse(
            action=request.action,
            title="Break-Even Chart",
            content=content,
            grounding_references=[_report_ref("chart_data.break_even_comparison")],
            metadata={"available": bool(report.chart_data.break_even_comparison)},
        )

    if "sensitivity" in metric:
        available = bool(report.chart_data.sensitivity_ranking)
        content = (
            "The sensitivity ranking is copied from deterministic Decision Analytics."
            if available
            else "No authoritative sensitivity ranking is available in this report."
        )
        return ReportActionResponse(
            action=request.action,
            title="Sensitivity Chart",
            content=content,
            grounding_references=[_report_ref("chart_data.sensitivity_ranking")],
            metadata={"available": available},
        )

    return ReportActionResponse(
        action=request.action,
        title="Chart Explanation",
        content=(
            "Specify break-even, sensitivity, or monthly projection to explain a "
            "persisted chart dataset."
        ),
        grounding_references=[],
        metadata={"available": False},
    )


def _what_could_change(
    *, report: StructuredReport, action: ReportActionType
) -> ReportActionResponse:
    decision_changes = report.decision.what_could_change
    sensitivity = report.chart_data.sensitivity_ranking

    sensitivity_lines: list[str] = []
    for item in sensitivity:
        name = item.get("input_name")
        rank = item.get("rank")
        impact = item.get("max_abs_ranking_metric_change_percent")
        if name:
            text = str(name)
            if rank is not None:
                text += f" — rank {rank}"
            if impact is not None:
                text += f" — max absolute modeled impact {impact}%"
            sensitivity_lines.append(text)

    content = (
        "### What Could Change the Decision\n\n"
        "**Final Decision conditions**\n"
        + _lines(
            decision_changes,
            empty_message="No explicit decision-flip conditions are recorded.",
        )
        + "\n\n**Deterministic sensitivity ranking**\n"
        + _lines(
            sensitivity_lines,
            empty_message="No sensitivity ranking is available.",
        )
    )
    return ReportActionResponse(
        action=action,
        title="What Could Change",
        content=content,
        grounding_references=[
            _report_ref("decision.what_could_change"),
            _report_ref("chart_data.sensitivity_ranking"),
        ],
    )


def _grounded_summary(
    *, report: StructuredReport, request: ReportActionRequest, simple: bool = False
) -> ReportActionResponse:
    decision = report.decision
    question = (request.question or "").strip()
    heading = "Simple Report Summary" if simple else "Grounded Report Summary"

    content = (
        f"### {heading}\n\n"
        + (f"**Question:** {question}\n\n" if question else "")
        + f"**Decision:** {decision.decision.value}\n"
        + f"**Confidence:** {decision.confidence.value}\n\n"
        + f"**Grounded rationale:** {decision.rationale}\n\n"
        + "**Strongest recorded positive signals**\n"
        + _lines(
            decision.strongest_positive_signals,
            empty_message="No positive signals are recorded in the Final Decision.",
        )
        + "\n\n**Strongest recorded negative signals**\n"
        + _lines(
            decision.strongest_negative_signals,
            empty_message="No negative signals are recorded in the Final Decision.",
        )
        + "\n\n**Recommended next steps**\n"
        + _lines(
            decision.recommended_next_steps,
            empty_message="No next steps are recorded in the Final Decision.",
        )
    )
    if question:
        content += (
            "\n\nThis deterministic response is intentionally limited to persisted report "
            "facts. A bounded LLM synthesis may later phrase a more specific answer, "
            "but it must use the same report evidence and cannot invent new facts."
        )

    return ReportActionResponse(
        action=request.action,
        title=heading,
        content=content,
        grounding_references=[
            _report_ref("decision.decision"),
            _report_ref("decision.confidence"),
            _report_ref("decision.rationale"),
            _report_ref("decision.strongest_positive_signals"),
            _report_ref("decision.strongest_negative_signals"),
            _report_ref("decision.recommended_next_steps"),
        ],
    )


def handle_report_action(
    *, report: StructuredReport, request: ReportActionRequest
) -> ReportActionResponse:
    if request.action == ReportActionType.SHOW_SOURCES:
        return _show_sources(report=report, action=request.action)
    if request.action == ReportActionType.SHOW_EVIDENCE:
        return _show_evidence(report=report, request=request)
    if request.action == ReportActionType.EXPLAIN_CALCULATION:
        metric = (request.target_metric or "").strip().lower()
        if not metric or "break_even" in metric or "breakeven" in metric:
            return _break_even_action(report=report, action=request.action)
        return ReportActionResponse(
            action=request.action,
            title="Calculation Explanation",
            content=(
                f"No deterministic calculation explainer is registered for '{metric}'. "
                "VentureMind will not invent a formula."
            ),
            grounding_references=[],
            metadata={"available": False},
        )
    if request.action == ReportActionType.EXPLAIN_CHART:
        return _explain_chart(report=report, request=request)
    if request.action == ReportActionType.CHALLENGE_CONCLUSION:
        return _challenge_conclusion(report=report, action=request.action)
    if request.action == ReportActionType.WHAT_COULD_CHANGE:
        return _what_could_change(report=report, action=request.action)
    if request.action == ReportActionType.EXPLAIN_SIMPLY:
        return _grounded_summary(report=report, request=request, simple=True)

    # EXPLAIN and ASK_VENTUREMIND are deliberately conservative here. The same
    # Chat AI can later perform bounded natural-language synthesis over selected
    # report context; this deterministic fallback never fabricates report facts.
    return _grounded_summary(report=report, request=request, simple=False)
