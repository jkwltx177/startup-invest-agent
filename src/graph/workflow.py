from langgraph.graph import StateGraph, START, END
from src.graph.state import GraphState
from src.agents.supervisor import Supervisor
from src.agents.discovery import DiscoveryAgent
from src.agents.tech_summary import TechSummaryAgent
from src.agents.market_eval import MarketEvalAgent
from src.agents.competitor import CompetitorAgent
from src.agents.decision import InvestmentDecisionAgent
from src.agents.report_gen import ReportAgent

def create_workflow():
    # Initialize Agents
    supervisor = Supervisor()
    discovery = DiscoveryAgent()
    tech_summary = TechSummaryAgent()
    market_eval = MarketEvalAgent()
    competitor = CompetitorAgent()
    decision = InvestmentDecisionAgent()
    report_gen = ReportAgent()

    # Create Graph
    workflow = StateGraph(GraphState)

    # Add Nodes
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("discovery", discovery)
    workflow.add_node("tech_summary", tech_summary)
    workflow.add_node("market_eval", market_eval)
    workflow.add_node("competitor", competitor)
    workflow.add_node("decision", decision)
    workflow.add_node("report_gen", report_gen)

    # Define Edges
    workflow.add_edge(START, "supervisor")
    
    # Conditional logic for Supervisor
    def supervisor_router(state: GraphState):
        next_agent = state.get("next_agent")
        if next_agent == "discovery":
            return "discovery"
        if next_agent == "workers":
            # For simplicity in this graph, we fan-out
            return ["tech_summary", "market_eval", "competitor"]
        if next_agent == "decision":
            return "decision"
        if next_agent == "end":
            return END
        return END

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "discovery": "discovery",
            "tech_summary": "tech_summary",
            "market_eval": "market_eval",
            "competitor": "competitor",
            "decision": "decision",
            "end": END
        }
    )

    # Workers back to Supervisor for consolidation/routing
    workflow.add_edge("discovery", "supervisor")
    workflow.add_edge("tech_summary", "supervisor")
    workflow.add_edge("market_eval", "supervisor")
    workflow.add_edge("competitor", "supervisor")

    # Decision Node router (Hold -> back to Supervisor)
    def decision_router(state: GraphState):
        results = state.get("validation_results", [])
        if not results:
            return "supervisor"
        
        # If any startup passed, generate report
        if any(r.passed for r in results):
            return "report_gen"
        else:
            # 보류 (Hold) -> back to Supervisor for retry/refinement
            return "supervisor"

    workflow.add_conditional_edges(
        "decision",
        decision_router,
        {
            "report_gen": "report_gen",
            "supervisor": "supervisor"
        }
    )

    workflow.add_edge("report_gen", END)

    return workflow.compile()
