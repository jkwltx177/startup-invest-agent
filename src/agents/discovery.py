from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import StartupProfile
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field

# 여러 스타트업을 한 번에 받기 위한 래퍼 클래스
class StartupList(BaseModel):
    candidates: List[StartupProfile] = Field(description="List of identified semiconductor startups")

class QueryExpansion(BaseModel):
    sub_queries: List[str] = Field(description="List of sub-queries for broader search")

class DiscoveryAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(StartupList)
        self.expansion_llm = self.llm.with_structured_output(QueryExpansion)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- DISCOVERY AGENT: PRE-RETRIEVAL BRANCHING ---")
        question = state["question"]
        
        # 1. Query Expansion (Branching)
        expansion_prompt = f"""
        Expand the following user query into 3-4 specialized sub-queries for finding semiconductor startups.
        Focus on different parts of the value chain (AI chip, EDA, Fab AI, Design Automation).
        Query: {question}
        """
        expansion = self.expansion_llm.invoke(expansion_prompt)
        sub_queries = expansion.sub_queries if expansion else [question]
        print(f"Sub-queries generated: {sub_queries}")
        
        # 2. Parallel-ish Retrieval (Accumulating results from multiple sub-queries)
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
                
        # 3. Deduplicate and normalize
        unique_candidates = {c.name: c for c in all_candidates}.values()
        
        print(f"Found {len(unique_candidates)} unique candidates.")
        
        # Corrective Loop logic would be handled by Supervisor by incrementing iteration count if 0 candidates found
        return {"startup_candidates": list(unique_candidates)}
