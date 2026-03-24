from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import StartupProfile
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field

from src.utils.human_loop import human_approve


class StartupList(BaseModel):
    candidates: List[StartupProfile] = Field(description="List of identified semiconductor startups")


class QueryExpansion(BaseModel):
    sub_queries: List[str] = Field(description="List of sub-queries for broader search")


class DiscoveryAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(StartupList)
        self.expansion_llm = self.llm.with_structured_output(QueryExpansion)
        self.retriever = SemiconductorRetriever()
        self.top_k = 5

    def __call__(self, state: GraphState):
        print("\n>>> [discovery] 스타트업 발굴(RAG) 실행 중... (Top1~Top5)", flush=True)
        question = state["question"]

        expansion_prompt = f"""
        Expand the following user query into 3-4 specialized sub-queries for finding semiconductor startups.
        Focus on different parts of the value chain (AI chip, EDA, Fab AI, Design Automation).
        Query: {question}
        """
        expansion = self.expansion_llm.invoke(expansion_prompt)
        sub_queries = expansion.sub_queries if expansion else [question]
        print(f"Sub-queries generated: {sub_queries}", flush=True)

        all_candidates = []
        for q in sub_queries:
            context = self.retriever.get_context(q, k=5)

            extraction_prompt = f"""
            Identify and profile semiconductor startups from the following context for sub-query: {q}
            Context: {context}
            """
            try:
                result = self.structured_llm.invoke(extraction_prompt)
                if result and result.candidates:
                    all_candidates.extend(result.candidates)
            except Exception as e:
                print(f"Error in discovery for sub-query '{q}': {e}")

        unique_candidates = {c.name: c for c in all_candidates}.values()
        ranked = sorted(unique_candidates, key=lambda c: c.relevance_score, reverse=True)[: self.top_k]

        print(f"Found {len(ranked)} unique candidates (Top {self.top_k}).", flush=True)
        print("   " + ", ".join(c.name for c in ranked), flush=True)

        if not human_approve("discovery", f"발굴된 후보 {len(ranked)}건. 계속 진행하시겠습니까?"):
            return {"startup_candidates": []}

        return {"startup_candidates": list(ranked)}
