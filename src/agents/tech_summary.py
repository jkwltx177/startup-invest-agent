from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import TechSummary
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field


class TechSummaryList(BaseModel):
    summaries: List[TechSummary] = Field(description="List of technical summaries for each candidate")


class TechQualityCheck(BaseModel):
    is_sufficient: bool = Field(description="Whether the technical information is detailed and sourced")
    missing_elements: List[str] = Field(description="Elements missing from the analysis (e.g., TRL, Patent, Core Mechanism)")


class TechSummaryAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(TechSummaryList)
        self.quality_llm = self.llm.with_structured_output(TechQualityCheck)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("\n>>> [tech_summary] 기술 분석 실행 중...", flush=True)
        candidates = state.get("startup_candidates", [])
        target = (state.get("evaluation_target_name") or "").strip()
        if target:
            candidates = [c for c in candidates if (c.name or "").strip() == target]
        if not candidates:
            return {"tech_summaries": []}

        all_summaries = []
        for startup in candidates:
            print(f"Analyzing technology for {startup.name}...", flush=True)

            context = self.retriever.get_context(
                f"Technical architecture, core mechanism, and innovation of {startup.name} in {startup.domain}", k=6
            )

            prompt = f"""
            Identify and analyze the core technology of {startup.name} ({startup.domain}).
            Context: {context}

            Extract: tech_type, core_mechanism, application_area, differentiation, strengths, weaknesses.
            """

            try:
                result = self.structured_llm.invoke(prompt)
                summary = result.summaries[0] if result and result.summaries else None

                if summary:
                    summary.startup_name = startup.name
                    q_prompt = f"Verify if this summary of {startup.name} tech is sufficient based on context: {summary.model_dump_json()}\nContext: {context}"
                    quality = self.quality_llm.invoke(q_prompt)

                    if not quality.is_sufficient:
                        print(f"Warning: Tech summary for {startup.name} is lacking: {quality.missing_elements}")

                    all_summaries.append(summary)
            except Exception as e:
                print(f"Error in Tech Summary for {startup.name}: {e}")

        return {"tech_summaries": all_summaries}
