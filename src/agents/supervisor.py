from typing import Dict, Any
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from pydantic import BaseModel, Field


class PlanningResponse(BaseModel):
    plan: str = Field(description="Strategic plan for the current iteration")
    next_agent: str = Field(description="The next agent to call (discovery, workers, decision, report_gen, end)")
    is_done: bool = Field(description="Whether the entire process is complete")


class Supervisor:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.planner_llm = self.llm.with_structured_output(PlanningResponse)

    def judge_quality(self, state: GraphState) -> Dict[str, Any]:
        candidates = state.get("startup_candidates", [])
        tech = state.get("tech_summaries", [])
        market = state.get("market_analyses", [])

        coverage_score = 0
        if candidates:
            coverage_score += 0.3
        if tech and len(tech) >= len(candidates):
            coverage_score += 0.3
        if market and len(market) >= len(candidates):
            coverage_score += 0.4

        return {
            "score": coverage_score,
            "is_sufficient": coverage_score >= 0.9,
            "missing": "tech" if not tech else "market" if not market else "none",
        }

    def __call__(self, state: GraphState):
        current_iter = state.get("iteration_count", 0)
        print(f"\n>>> [supervisor] 실행 (Iteration: {current_iter})", flush=True)

        if current_iter >= 5:
            print("MAX ITERATIONS REACHED. FORCING REPORT GENERATION.", flush=True)
            return {"next_agent": "report_gen", "is_done": True}

        quality = self.judge_quality(state)

        prompt = f"""
        You are an investment supervisor for semiconductor AI startups.
        User Query: {state['question']}
        Current Iteration: {current_iter}
        Data Status:
        - Candidates: {len(state.get('startup_candidates', []))}
        - Tech Summaries: {len(state.get('tech_summaries', []))}
        - Market Analyses: {len(state.get('market_analyses', []))}

        Quality Score: {quality['score']}
        Sufficiency: {quality['is_sufficient']}

        Based on this, decide the next step.
        If candidates are missing, go to 'discovery'.
        If candidates exist but tech or market data is missing/incomplete, go to 'workers'.
        If everything is sufficient, go to 'decision'.
        If decision is already made and passed, go to 'report_gen'.
        """

        result = self.planner_llm.invoke(prompt)
        print(f"Supervisor Plan: {result.plan}", flush=True)

        return {
            "next_agent": result.next_agent,
            "iteration_count": current_iter + 1,
            "is_done": result.is_done,
        }
