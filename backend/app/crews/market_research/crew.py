from crewai import (
    Agent,
    Crew,
    Process,
    Task,
)
from crewai.llms.base_llm import BaseLLM
from crewai.tools.base_tool import BaseTool

from app.schemas.analysis import AnalysisStage
from app.schemas.research import (
    MarketAnalysis,
    ResearchStageClaim,
)


class MarketResearchCrewError(
    RuntimeError
):
    pass


class MarketResearchCrewRunner:
    def __init__(
        self,
        *,
        llm: BaseLLM,
        research_tool: BaseTool,
    ) -> None:
        self._llm = llm
        self._research_tool = research_tool

    def build_crew(self) -> Crew:
        market_agent = Agent(
            role="Market Research Analyst",
            goal=(
                "Evaluate the target market using "
                "evidence and clearly distinguish "
                "observed facts from inference."
            ),
            backstory=(
                "You are a disciplined market "
                "research analyst. You investigate "
                "market size, demand signals, trends, "
                "barriers, regulation, and distribution. "
                "You never invent sources or present "
                "unsupported claims as observed facts."
            ),
            llm=self._llm,
            allow_delegation=False,
            max_iter=6,
            verbose=False,
        )

        market_task = Task(
            description=(
                "RESEARCH SUBJECT LOCK:\n"

"- Your research subject is the market "
"for the venture described in the "
"FROZEN IDEA PROFILE.\n"

"- Do NOT research the market research "
"industry merely because your role is "
"called Market Research Analyst.\n"

"- Only research the market-research "
"services industry if the venture itself "
"sells market-research products or "
"services.\n"

"- Before searching, identify the "
"venture or product, target customers, "
"and target geography from the profile.\n"

"- Every search query must be directly "
"relevant to the venture, its target "
"customers, its target geography, "
"demand, adoption, market size, "
"barriers, regulation, or distribution.\n"

"- Include the target geography in search "
"queries whenever geography materially "
"affects the market.\n"

"- Never substitute a different industry "
"or broader unrelated market because "
"evidence for the actual venture is "
"difficult to find.\n"

"- If reliable evidence about the actual "
"target market is unavailable, return "
"INSUFFICIENT evidence and explain the "
"limitation instead of researching a "
"different market.\n\n"

"Rules:\n"

"- Never invent sources or source IDs.\n"

"- Only use source IDs returned by the "
"research tool.\n"

"- Every WEB source you rely on must be "
"copied into evidence_sources.\n"

"- Preserve the exact source_id, title, "
"and URL returned by the research tool.\n"

"- Use WEB as the provenance for web "
"search evidence.\n"

"- The source snippet may be used as the "
"evidence excerpt when appropriate.\n"

"- Every OBSERVED finding must reference "
"one or more exact source IDs through "
"evidence_source_ids.\n"

"- Every evidence_source_id must match "
"a source present in evidence_sources.\n"

"- Clearly separate observation from "
"inference.\n"

"- Numerical claims require evidence.\n"

"- If reliable evidence is unavailable, "
"say so and lower evidence quality.\n"

"- INSUFFICIENT_EVIDENCE is an acceptable "
"outcome."
            ),
            expected_output=(
                "A structured MarketAnalysis containing "
                "a market summary, findings, evidence "
                "sources, evidence quality, and "
                "limitations."
            ),
            agent=market_agent,
            tools=[
                self._research_tool,
            ],
            output_pydantic=MarketAnalysis,
        )

        return Crew(
            agents=[
                market_agent,
            ],
            tasks=[
                market_task,
            ],
            process=Process.sequential,
            verbose=False,
        )

    def __call__(
        self,
        claim: ResearchStageClaim,
    ) -> MarketAnalysis:
        if (
            claim.stage
            != AnalysisStage.MARKET_RESEARCH
        ):
            raise MarketResearchCrewError(
                "Market research crew received "
                "a non-market research stage"
            )

        crew = self.build_crew()

        result = crew.kickoff(
            inputs={
                "profile_snapshot": (
                    claim
                    .profile_snapshot
                    .model_dump_json()
                ),
            }
        )

        if result.pydantic is None:
            raise MarketResearchCrewError(
                "Market research crew did not "
                "return structured output"
            )

        return MarketAnalysis.model_validate(
            result.pydantic
        )