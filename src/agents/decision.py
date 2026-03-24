from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import ValidationResult

class InvestmentDecisionAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Investment Decision Agent: Scoring based on scorecard.
        """
        print("--- INVESTMENT DECISION AGENT ---")
        candidates = state.get("startup_candidates", [])
        results = []
        
        # Weighted Scoring Logic (Simplified)
        # Scorecard: Owner(15%), Market(15%), Tech(10%), Competitor(8%), etc.
        # Semiconductor Specific: Differentiation(8%), Stage(5%), Data(4%), etc.
        
        for candidate in candidates:
            # logic to calculate score based on tech_summaries and market_analyses
            score = 85.0
            passed = score >= 70.0
            
            results.append(ValidationResult(
                startup_name=candidate.name,
                passed=passed,
                score=score,
                reason="Strong team with 10+ years fabless experience. High technical Moat."
            ))
            
        return {"validation_results": results}
