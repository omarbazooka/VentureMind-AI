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
                "Validation into an authoritative, grounded investment recommendation "
                "(GO, CONDITIONAL_GO, NO_GO, or INSUFFICIENT_EVIDENCE) with explicit "
                "rationale, limitations, and key conditions."
            ),
            backstory=(
                "You are an experienced venture capitalist chairing an investment "
                "committee. You base your decisions solely on the supplied evidence "
                "and rigorous analysis. You do not fabricate data, promise guaranteed "
                "success, or exceed the confidence supported by the evidence. You "
                "perform NO web research and use NO external tools."
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
                "- Decision must be one of: GO, CONDITIONAL_GO, NO_GO, INSUFFICIENT_EVIDENCE.\n"
                "- Confidence must be one of: HIGH, MEDIUM, LOW.\n"
                "- If Research Evidence Gate or Independent Validation notes insufficient "
                "evidence, do NOT claim HIGH confidence.\n"
                "- Detail the strongest positive and negative signals.\n"
                "- Provide clear rationale and what assumptions could change the decision.\n"
                "- List recommended next validation steps."
            ),
            expected_output=(
                "A structured FinalDecisionDraft containing decision, confidence, "
                "rationale, supporting_evidence_lineage, strongest_positive_signals, "
                "strongest_negative_signals, critical_assumptions, limitations, "
                "what_could_change, and recommended_next_steps."
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
