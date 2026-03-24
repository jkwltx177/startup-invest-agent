from typing import List, Dict
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field


class CompetitorProfile(BaseModel):
    name: str = Field(description="Name of the competitor")
    core_tech: str = Field(description="Core technology of the competitor")
    market_share: str = Field(description="Estimated market position")
    differentiation: str = Field(description="How the target startup differs from this competitor")


class CompetitorList(BaseModel):
    competitors: List[CompetitorProfile] = Field(description="List of key competitors for the target startup")


class CompetitorAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(CompetitorList)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("\n>>> [competitor] 경쟁사 분석 실행 중...", flush=True)
        candidates = state.get("startup_candidates", [])
        target = (state.get("evaluation_target_name") or "").strip()
        if target:
            candidates = [c for c in candidates if (c.name or "").strip() == target]
        if not candidates:
            return {"active_agents": ["competitor_skipped"]}

        for startup in candidates:
            print(f"Finding competitors for {startup.name}...", flush=True)

            context = self.retriever.get_context(
                f"Direct and indirect competitors of {startup.name} in {startup.domain} semiconductor space",
                k=6,
            )

            prompt = f"""
            Identify the top 3 competitors for {startup.name}.
            Compare their core tech and market position.
            Context: {context}
            """

            try:
                result = self.structured_llm.invoke(prompt)
                if result and result.competitors:
                    pass
            except Exception as e:
                print(f"Error in Competitor Analysis for {startup.name}: {e}")

        return {"active_agents": ["competitor_done"]}
