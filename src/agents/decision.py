from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import ValidationResult
from pydantic import BaseModel, Field

class ValidationResultList(BaseModel):
    results: List[ValidationResult] = Field(description="Scoring results for each candidate")

class InvestmentDecisionAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(ValidationResultList)

    def __call__(self, state: GraphState):
        print("--- INVESTMENT DECISION AGENT: FINAL SCORING ---")
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])
        
        # 실제 분석된 데이터를 프롬프트에 결합
        prompt = f"""
        As a lead investment partner, evaluate the following startups based on the collected analysis.
        
        Candidates: {candidates}
        Technical Analysis: {tech_summaries}
        Market Analysis: {market_analyses}
        
        Apply the scorecard method (Owner 15%, Market 15%, Tech 10%, etc.).
        A startup 'passes' if the score is 70 or above.
        Provide a detailed reason for each score.
        """
        
        try:
            result = self.structured_llm.invoke(prompt)
            results = result.results if result else []
        except Exception as e:
            print(f"Error in Decision Structured Output: {e}")
            results = []
            
        return {"validation_results": results}
