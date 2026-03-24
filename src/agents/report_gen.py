from langchain_openai import ChatOpenAI
from src.graph.state import GraphState

class ReportAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name)

    def __call__(self, state: GraphState):
        """
        Report Generation Agent: Synthesis of all data into a markdown report.
        """
        print("--- REPORT AGENT ---")
        candidates = state.get("startup_candidates", [])
        tech = state.get("tech_summaries", [])
        market = state.get("market_analyses", [])
        results = state.get("validation_results", [])
        
        # Report Template based on design-deliverables.md
        # 0. Executive Summary
        # 1. Company Status
        # 2. Investment Structure
        # 3. Financial/Bessemer Metrics
        # 4. Business & Market (AI focused)
        # 5. Profit/Loss Projections
        # 6. Valuation & ROI
        # 7. Final Opinion
        
        report = f"# Semiconductor AI Startup Investment Report\n\nAnalyzed {len(candidates)} startups."
        
        return {"final_report": report, "is_done": True}
