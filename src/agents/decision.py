from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import ValidationResult
from pydantic import BaseModel, Field

from src.utils.human_loop import human_approve


class ValidationResultList(BaseModel):
    results: List[ValidationResult] = Field(description="Scoring results for each candidate")


class InvestmentDecisionAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(ValidationResultList)

    def __call__(self, state: GraphState):
        print("\n>>> [decision] 투자 결정 실행 중... (Top1~Top5 순 평가)", flush=True)
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])

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

        all_hold = len(results) > 0 and all(not r.passed for r in results)
        print(
            f"   [decision] 통과 {sum(1 for r in results if r.passed)}건 / 보류 {sum(1 for r in results if not r.passed)}건"
            + (" → 전부 보류" if all_hold else ""),
            flush=True,
        )

        if not human_approve("decision", "투자 결정 결과. 보고서 생성 진행하시겠습니까?"):
            return {"validation_results": [], "all_hold": all_hold}

        return {"validation_results": results, "all_hold": all_hold}
