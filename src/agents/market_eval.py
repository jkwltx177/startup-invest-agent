from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import MarketAnalysis
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field

class MarketAnalysisList(BaseModel):
    analyses: List[MarketAnalysis] = Field(description="List of market analyses for each candidate")

class MarketEvalAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(MarketAnalysisList)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- MARKET EVAL AGENT: ANALYZING MARKET DATA FROM PDF ---")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"market_analyses": []}

        # 모든 후보자에 대한 통합 컨텍스트 검색
        candidate_names = ", ".join([c.name for d in candidates])
        context = self.retriever.get_context(f"Market analysis, TAM, SAM, SOM, CAGR for: {candidate_names}", k=10)
        
        prompt = f"""
        Analyze the market potential for the following startups using the context provided.
        Context: {context}
        
        Startups to analyze: {[c.name for c in candidates]}
        
        Extract TAM/SAM/SOM and growth rate (CAGR) if available in the reports (like Samsung/SK Hynix or trend reports).
        """
        
        try:
            result = self.structured_llm.invoke(prompt)
            market_analyses = result.analyses if result else []
        except Exception as e:
            print(f"Error in Market Eval Structured Output: {e}")
            market_analyses = []
            
        return {"market_analyses": market_analyses}
