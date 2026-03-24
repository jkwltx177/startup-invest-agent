from langchain_openai import ChatOpenAI
from src.graph.state import GraphState

class Supervisor:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Master Agent: Orchestrates the flow.
        Agents never communicate directly; they return to Supervisor.
        """
        print(f"--- SUPERVISOR (Iteration: {state.get('iteration_count', 0)}) ---")
        
        # 1. Start with discovery if no candidates found
        if not state.get("startup_candidates"):
            return {"next_agent": "discovery"}
        
        # 2. Once candidates exist, perform deep analysis
        # Check if analysis is complete for all candidates
        has_tech = len(state.get("tech_summaries", [])) >= len(state.get("startup_candidates", []))
        has_market = len(state.get("market_analyses", [])) >= len(state.get("startup_candidates", []))
        
        if not has_tech or not has_market:
            # Trigger parallel workers via the graph router
            return {"next_agent": "workers"}
            
        # 3. Decision phase
        if not state.get("validation_results"):
            return {"next_agent": "decision"}
            
        # 4. Final routing based on decision results
        # (This logic is also handled in the graph's conditional edges, 
        # but the supervisor can set flags or signals here)
        
        return {"next_agent": "end"}
