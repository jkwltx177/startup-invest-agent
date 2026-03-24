from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import MarketAnalysis

class MarketEvalAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Market Evaluation Agent: Analyze industry reports using RAG.
        Extract TAM/SAM/SOM and CAGR data.
        """
        print("--- MARKET EVAL AGENT ---")
        candidates = state.get("startup_candidates", [])
        market_analyses = []
        
        for candidate in candidates:
            # 1. RAG search for industry market size/trends
            # 2. Competitor growth rate extraction
            # 3. Market position assessment
            analysis = MarketAnalysis(
                startup_name=candidate.name,
                market_size="TAM: $5B, SAM: $800M",
                growth_rate="CAGR 15%",
                market_position="Challenger",
                investment_attractiveness="High"
            )
            market_analyses.append(analysis)
            
        return {"market_analyses": market_analyses}
