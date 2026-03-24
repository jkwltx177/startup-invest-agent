from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import StartupProfile

class DiscoveryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Discovery Agent: Search for startups using RAG and Web Search.
        """
        print("--- DISCOVERY AGENT ---")
        question = state["question"]
        
        # 1. Expand keywords (AI chip, EDA, etc.)
        # 2. RAG search (reports, news)
        # 3. Entity extraction
        
        # Skeleton output:
        candidates = [
            StartupProfile(
                name="FutureChip AI", 
                domain="AI chip", 
                investment_stage="Series B",
                description="Specializing in ultra-low power NPU for edge computing.",
                relevance_score=0.95
            )
        ]
        
        return {"startup_candidates": candidates}
