from typing import List, Dict
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
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(TechSummaryList)
        self.quality_llm = self.llm.with_structured_output(TechQualityCheck)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- TECH SUMMARY AGENT: INDIVIDUAL ANALYSES WITH QUALITY CHECK ---")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"tech_summaries": []}

        all_summaries = []
        for startup in candidates:
            print(f"Analyzing technology for {startup.name}...")
            
            # Individual Retrieval
            context = self.retriever.get_context(f"Technical architecture, core mechanism, and innovation of {startup.name} in {startup.domain}", k=6)
            
            prompt = f"""
            Identify and analyze the core technology of {startup.name} ({startup.domain}).
            Context: {context}
            
            Extract: tech_type, core_mechanism, application_area, differentiation, strengths, weaknesses.
            """
            
            try:
                # 1. Generate Summary
                result = self.structured_llm.invoke(prompt)
                summary = result.summaries[0] if result and result.summaries else None
                
                if summary:
                    # 2. Quality Check
                    q_prompt = f"Verify if this summary of {startup.name} tech is sufficient based on context: {summary.json()}\nContext: {context}"
                    quality = self.quality_llm.invoke(q_prompt)
                    
                    if not quality.is_sufficient:
                        print(f"Warning: Tech summary for {startup.name} is lacking: {quality.missing_elements}")
                        # (Optional: One-time retry with broader search)
                    
                    all_summaries.append(summary)
            except Exception as e:
                print(f"Error in Tech Summary for {startup.name}: {e}")
            
        return {"tech_summaries": all_summaries}
