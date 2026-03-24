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
    supervisor = Supervisor()
    discovery = DiscoveryAgent()
    tech_summary = TechSummaryAgent()
    market_eval = MarketEvalAgent()
    competitor = CompetitorAgent()
    decision = InvestmentDecisionAgent()
    report_gen = ReportAgent()

    workflow = StateGraph(GraphState)

    workflow.add_node("supervisor", supervisor)
    workflow.add_node("discovery", discovery)
    workflow.add_node("tech_summary", tech_summary)
    workflow.add_node("market_eval", market_eval)
    workflow.add_node("competitor", competitor)
    workflow.add_node("decision", decision)
    workflow.add_node("report_gen", report_gen)

    workflow.add_edge(START, "supervisor")

    def supervisor_router(state: GraphState):
        n = state.get("next_agent")
        if n == "discovery":
            return "discovery"
        if n == "tech_summary":
            return "tech_summary"
        if n == "report_gen":
            return "report_gen"
        return END

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "discovery": "discovery",
            "tech_summary": "tech_summary",
            "report_gen": "report_gen",
            END: END,
        },
    )

    workflow.add_edge("discovery", "supervisor")
    workflow.add_edge("tech_summary", "market_eval")
    workflow.add_edge("market_eval", "competitor")
    workflow.add_edge("competitor", "decision")

    def after_decision(state: GraphState):
        if state.get("last_decision_passed"):
            return "report_gen"
        return "supervisor"

    workflow.add_conditional_edges(
        "decision",
        after_decision,
        {"report_gen": "report_gen", "supervisor": "supervisor"},
    )

    workflow.add_edge("report_gen", END)

    return workflow.compile()
