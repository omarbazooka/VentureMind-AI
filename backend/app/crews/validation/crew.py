import json

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM
from pydantic import BaseModel

from app.schemas.validation import ValidationDraft
from app.schemas.validation_runtime import ValidationAnalysisContext


class ValidationCrewError(RuntimeError):
    pass


def _serialize_input(value: BaseModel | None) -> str:
    if value is None:
        return "null"
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
    )


class ValidationCrewRunner:
    def __init__(self, *, llm: BaseLLM) -> None:
        self._llm = llm
        self._has_executed = False

    def build_crew(self) -> Crew:
        validator_agent = Agent(
            role="Independent Venture Validator",
            goal=(
                "Critically evaluate the complete venture analysis across Market, "
                "Competitors, Customers, Strategy, Finance, Decision Analytics, and "
                "Risk. Identify unsupported claims, contradictory conclusions, and "
                "unreflected risks without performing new research or inventing facts."
            ),
            backstory=(
                "You are a rigorous, independent venture auditor and investment "
                "committee prep validator. Your job is to challenge overoptimistic "
                "assumptions, verify that claims are supported by concrete evidence, "
                "ensure risks are reflected downstream, and flag sensitivity oversights. "
                "You do NOT browse the web or use external tools."
            ),
            llm=self._llm,
            allow_delegation=False,
            max_iter=4,
            verbose=False,
        )

        validation_task = Task(
            description=(
                "Produce a structured ValidationDraft auditing the supplied venture "
                "analysis.\n\n"
                "CONTEXT:\n"
                "- Frozen Idea Profile: {profile_snapshot}\n"
                "- Research Evidence Gate: {research_gate}\n"
                "- Market Analysis: {market_analysis}\n"
                "- Competitor Analysis: {competitor_analysis}\n"
                "- Customer Analysis: {customer_analysis}\n"
                "- Business Strategy: {business_strategy}\n"
                "- Finance Bundle: {finance_bundle}\n"
                "- Decision Analytics: {decision_analytics}\n"
                "- Risk Analysis: {risk_analysis}\n\n"
                "INSPECTION RESPONSIBILITIES:\n"
                "- Check for unsupported or contradictory claims across stages.\n"
                "- Check if decision logic ignores sensitivity or downside scenarios.\n"
                "- Check if critical risks identified in Risk analysis are ignored in Strategy/Finance.\n"
                "- Check if research evidence gaps are acknowledged as uncertainty rather than certainty.\n"
                "- Every ordinary issue MUST cite concrete lineage using one or more of: "
                "profile_fields, evidence_ids, financial_metrics, decision_kpis, "
                "sensitivity_inputs, or risk_titles.\n"
                "- affected_stages describe where the problem exists; stage names alone are NOT evidence.\n"
                "- The only stage-only exception is MISSING_EVIDENCE for a research stage that the supplied "
                "Research Evidence Gate itself marks insufficient.\n"
                "- For any issue, specify category, severity, description, affected stages, concrete lineage, "
                "and an optional suggestion.\n"
                "- Do NOT decide retry scheduling, attempt counts, execution order, or state mutation. "
                "Application code owns those decisions.\n"
                "- Return ValidationDraft only. Do NOT invent new facts or web citations."
            ),
            expected_output=(
                "A structured ValidationDraft containing executive_assessment, "
                "a list of concretely grounded ValidationIssue items, and limitations."
            ),
            agent=validator_agent,
            tools=[],
            output_pydantic=ValidationDraft,
        )

        return Crew(
            agents=[validator_agent],
            tasks=[validation_task],
            process=Process.sequential,
            verbose=False,
        )

    def __call__(
        self,
        context: ValidationAnalysisContext,
    ) -> ValidationDraft:
        if self._has_executed:
            raise ValidationCrewError("Validation runner is single-use")

        self._has_executed = True
        crew = self.build_crew()

        result = crew.kickoff(
            inputs={
                "profile_snapshot": _serialize_input(context.profile_snapshot),
                "research_gate": _serialize_input(context.research_gate),
                "market_analysis": _serialize_input(context.market_analysis),
                "competitor_analysis": _serialize_input(context.competitor_analysis),
                "customer_analysis": _serialize_input(context.customer_analysis),
                "business_strategy": _serialize_input(context.business_strategy),
                "finance_bundle": _serialize_input(context.finance_bundle),
                "decision_analytics": _serialize_input(context.decision_analytics),
                "risk_analysis": _serialize_input(context.risk_analysis),
            }
        )

        if result.pydantic is None:
            raise ValidationCrewError(
                "Validation crew did not return structured output"
            )

        return ValidationDraft.model_validate(result.pydantic)
