from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import StartupProfile
from src.tools.retriever import SemiconductorRetriever
import json

class DiscoveryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        """
        Discovery Agent: Search for startups using RAG.
        Returns candidates to be added to the shared state.
        """
        print("--- DISCOVERY AGENT: RAG SEARCH ---")
        question = state["question"]
        
        # 1. RAG 기반 기업 검색 (리포트, 기사 활용)
        context = self.retriever.get_context(f"Startups related to: {question}")
        
        # 2. LLM을 통한 엔티티 추출 (기업명, 기술 분야, 투자 단계)
        prompt = f"""
        Based on the following context, identify promising semiconductor AI startups.
        Context: {context}
        
        User Query: {question}
        
        Return the result as a list of JSON objects with keys: 
        "name", "domain", "investment_stage", "description", "relevance_score".
        """
        
        response = self.llm.invoke(prompt)
        
        # 3. Parsing (Simple extraction logic)
        try:
            # Note: In production, use structured output (LLM with tools/schema)
            # For skeleton, we simulate the output list
            raw_content = response.content
            # Simulating output for stability in skeleton
            candidates = [
                StartupProfile(
                    name="FutureChip AI", 
                    domain="AI chip", 
                    investment_stage="Series B",
                    description="Specializing in ultra-low power NPU for edge computing.",
                    relevance_score=0.95
                )
            ]
        except Exception as e:
            print(f"Error parsing discovery results: {e}")
            candidates = []
        
        return {"startup_candidates": candidates}
