import json

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM
from pydantic import BaseModel

from app.schemas.decision import FinalDecisionDraft
from app.schemas.decision_runtime import InvestmentCommitteeContext


class DecisionCrewError(RuntimeError):
    pass


def _serialize_input(value: BaseModel | None) -> str:
    if value is None:
        return "null"
    return json.dumps(
        value.model_dump(mode="json"),
        ensure_ascii=False,
    )


class DecisionCrewRunner:
    def __init__(self, *, llm: BaseLLM) -> None:
        self._llm = llm
        self._has_executed = False

    def build_crew(self) -> Crew:
        committee_agent = Agent(
            role="Investment Committee Chair",
            goal=(
                "Synthesize the validated venture findings across Market, Competitors, "
                "Customers, Strategy, Finance, Analytics, Risk, and Independent "
                "Validation into a grounded investment recommendation "
                "(GO, CONDITIONAL_GO, NO_GO, or INSUFFICIENT_EVIDENCE) with explicit "
                "rationale, limitations, and key conditions."
            ),
            backstory=(
                "You are an experienced venture capitalist chairing an investment "
                "committee. You base decisions solely on the supplied validated packet. "
                "You do not fabricate data, promise guaranteed success, or exceed the "
                "confidence supported by evidence. You perform NO web research and use "
                "NO external tools."
            ),
            llm=self._llm,
            allow_delegation=False,
            max_iter=4,
            verbose=False,
        )

        decision_task = Task(
            description=(
                "Produce a structured FinalDecisionDraft synthesizing the complete "
                "decision packet.\n\n"
                "CONTEXT:\n"
                "- Frozen Idea Profile: {profile_snapshot}\n"
                "- Research Evidence Gate: {research_gate}\n"
                "- Market Analysis: {market_analysis}\n"
                "- Competitor Analysis: {competitor_analysis}\n"
                "- Customer Analysis: {customer_analysis}\n"
                "- Business Strategy: {business_strategy}\n"
                "- Finance Bundle: {finance_bundle}\n"
                "- Decision Analytics: {decision_analytics}\n"
                "- Risk Analysis: {risk_analysis}\n"
                "- Independent Validation: {validation_analysis}\n\n"
                "RULES:\n"
                "- Decision must be one of GO, CONDITIONAL_GO, NO_GO, INSUFFICIENT_EVIDENCE.\n"
                "- Confidence must be HIGH, MEDIUM, or LOW, but deterministic application guardrails may cap it.\n"
                "- Use NO new web research or external tools.\n"
                "- supporting_evidence_lineage MUST contain concrete structured references, not free-form stage names.\n"
                "- Allowed lineage kinds are PROFILE_FIELD, EVIDENCE_SOURCE, FINANCIAL_METRIC, DECISION_KPI, "
                "SENSITIVITY_INPUT, RISK, and VALIDATION_ISSUE.\n"
                "- For EVIDENCE_SOURCE include the exact supplied source_id and its research stage.\n"
                "- For FINANCIAL_METRIC use the exact metric enum value and stage FINANCE.\n"
                "- For DECISION_KPI or SENSITIVITY_INPUT use exact supplied values and stage DECISION_ANALYTICS.\n"
                "- For RISK use an exact supplied risk title and stage RISK.\n"
                "- For VALIDATION_ISSUE use an exact supplied validation issue category and stage INDEPENDENT_VALIDATION.\n"
                "- PROFILE_FIELD uses an exact key from the frozen profile and no stage.\n"
                "- Never use a stage name by itself as evidence lineage.\n"
                "- Detail strongest positive and negative signals, assumptions, limitations, what could change, "
                "and recommended next validation steps."
            ),
            expected_output=(
                "A structured FinalDecisionDraft containing decision, confidence, "
                "rationale, concrete supporting_evidence_lineage references, "
                "strongest_positive_signals, strongest_negative_signals, critical_assumptions, "
                "limitations, what_could_change, and recommended_next_steps."
            ),
            agent=committee_agent,
            tools=[],
            output_pydantic=FinalDecisionDraft,
        )

        return Crew(
            agents=[committee_agent],
            tasks=[decision_task],
            process=Process.sequential,
            verbose=False,
        )

    def __call__(
        self,
        context: InvestmentCommitteeContext,
    ) -> FinalDecisionDraft:
        if self._has_executed:
            raise DecisionCrewError("Decision runner is single-use")

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
                "validation_analysis": _serialize_input(context.validation_analysis),
            }
        )

        if result.pydantic is None:
            raise DecisionCrewError(
                "Investment Committee crew did not return structured output"
            )

        return FinalDecisionDraft.model_validate(result.pydantic)
