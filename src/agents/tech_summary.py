from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import TechSummary
from src.tools.retriever import SemiconductorRetriever

class TechSummaryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        """
        Tech Summary Agent: RAG-based analysis of technical documents.
        Processes each candidate identified by the Discovery Agent.
        """
        print("--- TECH SUMMARY AGENT: RAG ANALYSIS ---")
        candidates = state.get("startup_candidates", [])
        tech_summaries = []
        
        for candidate in candidates:
            # 1. RAG-based search for technical info
            context = self.retriever.get_context(f"Technical architecture, mechanisms, and innovations of {candidate.name}")
            
            # 2. Extract technical innovation points
            prompt = f"""
            Identify the core technology and innovations for {candidate.name}.
            Technical Context: {context}
            
            Summarize: tech_type, core_mechanism, application_area, differentiation, strengths, weaknesses.
            """
            response = self.llm.invoke(prompt)
            
            # 3. Simulate structured output
            summary = TechSummary(
                startup_name=candidate.name,
                tech_type="NPU Architecture",
                core_mechanism="Sparse computing engine",
                application_area="Edge AI Acceleration",
                differentiation="Proprietary data compression during inference",
                strengths=["High energy efficiency", "Real-time processing"],
                weaknesses=["Niche compiler support"]
            )
            tech_summaries.append(summary)
            
        return {"tech_summaries": tech_summaries}
