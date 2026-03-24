from typing import List, Dict
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import ValidationResult
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
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(CompetitorList)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- COMPETITOR AGENT: BRANCHING & FUSION ---")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"active_agents": ["competitor_skipped"]}

        all_competitors_summary = []
        for startup in candidates:
            print(f"Finding competitors for {startup.name}...")
            
            # Step 1: Branching Retrieval for competitors
            context = self.retriever.get_context(f"Direct and indirect competitors of {startup.name} in {startup.domain} semiconductor space", k=6)
            
            prompt = f"""
            Identify the top 3 competitors for {startup.name}.
            Compare their core tech and market position.
            Context: {context}
            """
            
            try:
                # 2. Fusion: Extract and profile
                result = self.structured_llm.invoke(prompt)
                if result and result.competitors:
                    all_competitors_summary.append({
                        "startup_name": startup.name,
                        "competitors": result.competitors
                    })
            except Exception as e:
                print(f"Error in Competitor Analysis for {startup.name}: {e}")
                
        # (Optional: Store detailed competitor info in state if needed)
        return {"active_agents": ["competitor_done"]}
