from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import TechSummary
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field

class TechSummaryList(BaseModel):
    summaries: List[TechSummary] = Field(description="List of technical summaries for each candidate")

class TechSummaryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(TechSummaryList)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- TECH SUMMARY AGENT: ANALYZING TECHNICAL SPECS FROM PDF ---")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"tech_summaries": []}

        # 후보 기업들의 기술적 키워드를 바탕으로 컨텍스트 검색
        tech_queries = ", ".join([f"{c.name} {c.domain} technology" for c in candidates])
        context = self.retriever.get_context(f"Technical details, architecture, and innovation: {tech_queries}", k=10)
        
        prompt = f"""
        Analyze the core technology and innovations for the following startups using the context provided.
        Context: {context}
        
        Startups to analyze: {[c.name for c in candidates]}
        
        Identify: tech_type, core_mechanism, application_area, differentiation, strengths, and weaknesses.
        Focus on technical Moat (moat) and specific semiconductor innovations.
        """
        
        try:
            result = self.structured_llm.invoke(prompt)
            tech_summaries = result.summaries if result else []
        except Exception as e:
            print(f"Error in Tech Summary Structured Output: {e}")
            tech_summaries = []
            
        return {"tech_summaries": tech_summaries}
