from langchain_openai import ChatOpenAI
from src.graph.state import GraphState

class Supervisor:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Master Agent: Orchestrates the flow and increments iteration count.
        """
        # 현재 iteration 확인 및 증가 준비
        current_iter = state.get("iteration_count", 0)
        print(f"--- SUPERVISOR (Iteration: {current_iter}) ---")
        
        # 무한 루프 방지 (최대 3회)
        if current_iter >= 3:
            print("MAX ITERATIONS REACHED. FORCING END.")
            return {"next_agent": "end", "is_done": True}

        # 1. Start with discovery
        if not state.get("startup_candidates"):
            return {"next_agent": "discovery", "iteration_count": current_iter + 1}
        
        # 2. Deep analysis
        has_tech = len(state.get("tech_summaries", [])) >= len(state.get("startup_candidates", []))
        has_market = len(state.get("market_analyses", [])) >= len(state.get("startup_candidates", []))
        
        if not has_tech or not has_market:
            return {"next_agent": "workers"}
            
        # 3. Decision phase
        if not state.get("validation_results"):
            return {"next_agent": "decision"}
            
        return {"next_agent": "end", "is_done": True}
