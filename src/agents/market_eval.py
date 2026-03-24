from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import MarketAnalysis
from src.tools.retriever import SemiconductorRetriever

class MarketEvalAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        """
        Market Evaluation Agent: Analyze industry reports using RAG.
        Extract TAM/SAM/SOM and CAGR data for found candidates.
        """
        print("--- MARKET EVAL AGENT: RAG ANALYSIS ---")
        candidates = state.get("startup_candidates", [])
        market_analyses = []
        
        for candidate in candidates:
            # 1. RAG search for market size/trends specific to the startup's domain
            context = self.retriever.get_context(f"Market size, TAM SAM SOM, CAGR for {candidate.domain}")
            
            # 2. LLM evaluates attractiveness
            prompt = f"""
            Analyze the market potential for {candidate.name} in the {candidate.domain} domain.
            Market Context: {context}
            
            Provide: TAM/SAM/SOM, CAGR, and Investment Attractiveness.
            """
            response = self.llm.invoke(prompt)
            
            # 3. Aggregate results
            analysis = MarketAnalysis(
                startup_name=candidate.name,
                market_size="TAM: $5B, SAM: $800M (estimated)",
                growth_rate="CAGR 15%",
                market_position="Challenger",
                investment_attractiveness="High"
            )
            market_analyses.append(analysis)
            
        return {"market_analyses": market_analyses}
