from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from src.graph.state import GraphState

class Supervisor:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Master Agent that controls the flow.
        Decides which agent to run next based on current state.
        """
        # Logic to determine next_agent
        # For prototype, we'll just set it manually or based on some conditions
        print("--- SUPERVISOR ---")
        
        # Determine current progress
        if not state.get("startup_candidates"):
            return {"next_agent": "discovery"}
        
        if not state.get("tech_summaries") or not state.get("market_analyses"):
            # Could run tech_summary and market_eval in parallel
            # For simplicity in this skeleton, we trigger them sequentially or as active agents
            return {"next_agent": "workers"} # Logic to trigger multiple
            
        if not state.get("final_report"):
            return {"next_agent": "decision"}
            
        return {"next_agent": "end"}
