from langchain_openai import ChatOpenAI
from src.graph.state import GraphState

class CompetitorAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Competitor Comparison Agent: Identify competitors and analyze differences.
        """
        print("--- COMPETITOR AGENT ---")
        
        # 1. Web search for similar startups
        # 2. Compare tech & market position
        # 3. Assess entry barriers
        
        return {"active_agents": ["competitor_done"]} # Dummy progress indicator
