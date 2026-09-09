from typing import Any

from app.schemas.report import StructuredReport
from app.schemas.report_action import (
    ReportActionRequest,
    ReportActionResponse,
    ReportActionType,
)


def handle_report_action(
    *,
    report: StructuredReport,
    request: ReportActionRequest,
) -> ReportActionResponse:
    action = request.action
    target_section = (request.target_section or "").lower()
    target_metric = (request.target_metric or "").lower()

    if action == ReportActionType.EXPLAIN_CALCULATION:
        if "break_even" in target_metric or "breakeven" in target_metric or not target_metric:
            base_assumptions = report.finance.base_scenario.get("assumptions", {})
            price = base_assumptions.get("selling_price_per_unit", {}).get("value", "N/A")
            currency = base_assumptions.get("selling_price_per_unit", {}).get("currency", "USD")
            var_cost = base_assumptions.get("variable_cost_per_unit", {}).get("value", "N/A")
            fixed_costs = base_assumptions.get("fixed_costs", {}).get("value", "N/A")

            be_comparison = report.chart_data.break_even_comparison
            base_be = next((item for item in be_comparison if item.get("scenario") == "BASE"), {})
            be_units = base_be.get("break_even_units", "N/A")
            be_rev = base_be.get("break_even_revenue", "N/A")

            try:
                cm_val = f"{float(price) - float(var_cost):.2f}"
            except (ValueError, TypeError):
                cm_val = "N/A"

            content = (
                f"### Break-Even Calculation Breakdown\n\n"
                f"**Formula:**\n"
                f"$$\\text{{Break-Even Volume}} = \\frac{{\\text{{Fixed Costs}}}}{{\\text{{Price per Unit}} - \\text{{Variable Cost per Unit}}}}$$\n\n"
                f"**Authoritative Base Scenario Inputs:**\n"
                f"- Selling Price per Unit: `{price} {currency}`\n"
                f"- Variable Cost per Unit: `{var_cost} {currency}`\n"
                f"- Contribution Margin per Unit: `{cm_val} {currency}`\n"
                f"- Fixed Costs: `{fixed_costs} {currency}/period`\n\n"
                f"**Result:**\n"
                f"- Break-Even Sales Volume: **{be_units} units**\n"
                f"- Break-Even Revenue: **{be_rev} {currency}**\n\n"
                f"Below this volume, the business operates at a net loss; above it, each additional unit contributes to operating profit."
            )
            return ReportActionResponse(
                action=action,
                title="Break-Even Calculation",
                content=content,
                grounding_references=["FINANCE:base_scenario", "FINANCE:break_even_units"],
                suggested_followups=[
                    "What happens if price drops by 10%?",
                    "How does upside scenario change break-even?",
                ],
                metadata={"metric": "break_even", "units": be_units, "revenue": be_rev},
            )
        else:
            return ReportActionResponse(
                action=action,
                title=f"Calculation for {target_metric}",
                content=f"Calculation details for {target_metric} are derived from verified financial scenarios.",
                grounding_references=["FINANCE"],
            )

    elif action == ReportActionType.CHALLENGE_CONCLUSION:
        dec = report.decision
        negatives = dec.strongest_negative_signals or ["No severe negative signals noted."]
        assumptions = dec.critical_assumptions or ["Fixed overhead remains controlled."]
        changes = dec.what_could_change or ["Conversion drops significantly."]
        limitations = dec.limitations or ["Pilot validation required."]

        content = (
            f"### Critical Stress-Test & Conclusion Challenges\n\n"
            f"**Current Recommendation:** `{dec.decision.value}` (Confidence: `{dec.confidence.value}`)\n\n"
            f"**Strongest Vulnerabilities Identified:**\n"
            + "\n".join(f"- {n}" for n in negatives)
            + "\n\n**Fragile Assumptions Under Stress:**\n"
            + "\n".join(f"- {a}" for a in assumptions)
            + "\n\n**Conditions That Would Flip Decision to NO-GO:**\n"
            + "\n".join(f"- {c}" for c in changes)
            + "\n\n**Known Assessment Limitations:**\n"
            + "\n".join(f"- {l}" for l in limitations)
        )
        return ReportActionResponse(
            action=action,
            title="Adversarial Conclusion Challenge",
            content=content,
            grounding_references=["INVESTMENT_COMMITTEE:decision", "RISK:risks"],
            suggested_followups=[
                "What pilot experiments de-risk these assumptions?",
                "Show sensitivity ranking",
            ],
        )

    elif action == ReportActionType.SHOW_SOURCES:
        if not report.sources:
            content = "No external web citations were registered for this report. Data relied on internal profiling and deterministic modeling."
        else:
            lines = [
                f"- **{s.title}** ({s.provenance}) - Stage: `{s.stage}`"
                + (f" [Link]({s.url})" if s.url else "")
                for s in report.sources
            ]
            content = "### Verified Evidence Sources\n\n" + "\n".join(lines)

        return ReportActionResponse(
            action=action,
            title="Report Evidence Sources",
            content=content,
            grounding_references=[s.source_id for s in report.sources],
            suggested_followups=["Show market evidence", "Explain research quality"],
        )

    elif action == ReportActionType.SHOW_EVIDENCE:
        if "market" in target_section:
            sec = report.market
            evidence_lines = [f"- {f.get('claim', str(f))}" for f in sec.findings]
            content = (
                f"### Market Research Evidence\n\n"
                f"**Evidence Quality:** `{sec.evidence_quality}`\n\n"
                + ("**Key Findings:**\n" + "\n".join(evidence_lines) if evidence_lines else "No specific claims recorded.")
                + f"\n\n**Limitations:** {', '.join(sec.limitations) or 'None'}"
            )
        elif "competitor" in target_section:
            sec = report.competitors
            comp_names = [c.get("name", "Unknown") for c in sec.competitors]
            content = (
                f"### Competitor Intelligence Evidence\n\n"
                f"**Evidence Quality:** `{sec.evidence_quality}`\n"
                f"**Tracked Competitors:** {', '.join(comp_names) or 'None'}\n\n"
                f"**Summary:** {sec.summary}"
            )
        else:
            content = f"### Evidence Grounding for {target_section or 'Evaluation'}\n\nEvidence was gathered across Market, Competitor, Customer, and Financial modeling stages."

        return ReportActionResponse(
            action=action,
            title=f"Evidence for {target_section.title() or 'Report'}",
            content=content,
            grounding_references=["MARKET_RESEARCH", "COMPETITOR_INTELLIGENCE", "CUSTOMER_INTELLIGENCE"],
        )

    elif action == ReportActionType.EXPLAIN_CHART:
        if "break_even" in target_metric:
            content = (
                "### Understanding the Break-Even Comparison Chart\n\n"
                "This visualization shows the required unit sales volume to cover all fixed and variable costs "
                "under Base, Upside, and Downside scenarios. The Downside scenario tests higher variable costs or lower pricing, "
                "requiring more units to reach zero profit."
            )
        elif "monthly" in target_metric or "projection" in target_metric:
            content = (
                "### Understanding the 12-Month Projections Chart\n\n"
                "This chart tracks expected monthly revenue ramp against operating costs and cumulative cash position. "
                "Initial months reflect conservative ramp-up before reaching steady-state volume."
            )
        else:
            content = (
                "### Visualization Overview\n\n"
                "Interactive charts summarize scenario break-even points, monthly cash projections, and risk distribution matrix."
            )

        return ReportActionResponse(
            action=action,
            title="Chart Explanation",
            content=content,
            grounding_references=["chart_data"],
            suggested_followups=["Explain break-even calculation", "Show sensitivity ranking"],
        )

    elif action == ReportActionType.EXPLAIN_SIMPLY:
        dec = report.decision.decision.value
        content = (
            f"### In Simple Terms (ELI5)\n\n"
            f"**The Bottom Line:** VentureMind rates this project as **{dec}**.\n\n"
            f"**Why?**\n"
            f"{report.decision.rationale}\n\n"
            f"**What you need to do next:**\n"
            + "\n".join(f"- {s}" for s in report.decision.recommended_next_steps)
        )
        return ReportActionResponse(
            action=action,
            title="Simple Summary",
            content=content,
            grounding_references=["INVESTMENT_COMMITTEE:decision"],
            suggested_followups=["Show financial details", "What are the biggest risks?"],
        )

    elif action == ReportActionType.WHAT_COULD_CHANGE:
        sensitivity_items = report.chart_data.sensitivity_ranking
        sens_lines = [
            f"- **{s.get('input_name')}** (Shock: ±{s.get('shock_percent')}%): "
            + ", ".join(f"{imp.get('metric_name')} changes by {imp.get('change_percent')}%" for imp in s.get("impacts", []))
            for s in sensitivity_items
        ]
        content = (
            "### Sensitivity & Key Variables\n\n"
            "Small shifts in these parameters have the greatest leverage on venture viability:\n\n"
            + ("\n".join(sens_lines) if sens_lines else "- Sensitivity analysis details captured in analytical report.")
            + "\n\n**Decision Flip Triggers:**\n"
            + "\n".join(f"- {c}" for c in report.decision.what_could_change)
        )
        return ReportActionResponse(
            action=action,
            title="What Could Change",
            content=content,
            grounding_references=["DECISION_ANALYTICS:sensitivity", "INVESTMENT_COMMITTEE:what_could_change"],
            suggested_followups=["Explain break-even calculation", "Challenge conclusion"],
        )

    else:  # ASK_VENTUREMIND or general EXPLAIN
        q = request.question or "Can you explain this report?"
        content = (
            f"### VentureMind Report Analysis\n\n"
            f"**In response to:** *\"{q}\"*\n\n"
            f"Based on the validated assessment for **{report.title}**:\n\n"
            f"- **Executive Decision:** `{report.decision.decision.value}` with `{report.decision.confidence.value}` confidence.\n"
            f"- **Key Strength:** {', '.join(report.decision.strongest_positive_signals) or 'Positive gross margin potential'}.\n"
            f"- **Key Watchpoint:** {', '.join(report.decision.strongest_negative_signals) or 'Execution & adoption velocity'}.\n"
            f"- **Validation Status:** `{report.validation.status}` ({report.validation.executive_assessment})\n\n"
            f"Feel free to click any metric or chart for detailed calculation formulas."
        )
        return ReportActionResponse(
            action=action,
            title="Grounded Q&A Response",
            content=content,
            grounding_references=["INVESTMENT_COMMITTEE", "INDEPENDENT_VALIDATION", "FINANCE"],
            suggested_followups=["Explain break-even calculation", "Challenge conclusion", "Show evidence"],
        )
