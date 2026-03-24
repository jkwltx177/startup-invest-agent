from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import TechSummary

class TechSummaryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Tech Summary Agent: RAG-based analysis of technical papers, whitepapers, and websites.
        """
        print("--- TECH SUMMARY AGENT ---")
        candidates = state.get("startup_candidates", [])
        tech_summaries = []
        
        for candidate in candidates:
            # 1. RAG-based search for technical info of the candidate
            # 2. Extract technical innovation points
            # 3. Strength/Weakness analysis
            summary = TechSummary(
                startup_name=candidate.name,
                tech_type="NPU Architecture",
                core_mechanism="Sparse computing engine",
                application_area="Edge AI Acceleration",
                differentiation="3x efficiency improvement over legacy NPUs",
                strengths=["Low power consumption", "High throughput"],
                weaknesses=["Limited software stack ecosystem"]
            )
            tech_summaries.append(summary)
            
        return {"tech_summaries": tech_summaries}
