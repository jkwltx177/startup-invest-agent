from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Send
from src.graph.state import GraphState
from src.agents.orchestrator import Orchestrator
from src.agents.supervisor import Supervisor
from src.agents.mini_supervisor import MiniSupervisor
from src.agents.discovery import DiscoveryAgent
from src.agents.tech_summary import TechSummaryAgent
from src.agents.market_eval import MarketEvalAgent
from src.agents.competitor import CompetitorAgent
from src.agents.judge_loop import JudgeLoop
from src.agents.decision import InvestmentDecisionAgent
from src.agents.report_gen import ReportAgent


def create_workflow():
    # ── 에이전트 초기화 ──
    orchestrator = Orchestrator()
    supervisor = Supervisor()
    mini_supervisor = MiniSupervisor()
    discovery = DiscoveryAgent()
    tech_summary = TechSummaryAgent()
    market_eval = MarketEvalAgent()
    competitor = CompetitorAgent()
    judge_loop = JudgeLoop()
    decision = InvestmentDecisionAgent()
    report_gen = ReportAgent()

    # ── 그래프 생성 ──
    workflow = StateGraph(GraphState)

    # ── 노드 등록 ──
    workflow.add_node("orchestrator", orchestrator)
    workflow.add_node("supervisor", supervisor)
    workflow.add_node("mini_supervisor", mini_supervisor)
    workflow.add_node("discovery", discovery)
    workflow.add_node("tech_summary", tech_summary)
    workflow.add_node("market_eval", market_eval)
    workflow.add_node("competitor", competitor)
    workflow.add_node("judge_loop", judge_loop)
    workflow.add_node("decision", decision)
    workflow.add_node("report_gen", report_gen)

    # ── 엣지 정의 ──

    # START → orchestrator
    workflow.add_edge(START, "orchestrator")

    # orchestrator → END (direct) | supervisor (pipeline)
    def orchestrator_router(state: GraphState):
        route_type = state.get("route_type", "pipeline")
        if route_type == "direct" or state.get("is_done", False):
            return END
        return "supervisor"

    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_router,
        {END: END, "supervisor": "supervisor"},
    )

    # supervisor → discovery | mini_supervisor | judge_loop | decision | END
    def supervisor_router(state: GraphState):
        next_agent = state.get("next_agent", "end")
        if next_agent == "discovery":
            return "discovery"
        if next_agent == "mini_supervisor":
            return "mini_supervisor"
        if next_agent == "judge_loop":
            return "judge_loop"
        if next_agent == "decision":
            return "decision"
        return END

    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "discovery": "discovery",
            "mini_supervisor": "mini_supervisor",
            "judge_loop": "judge_loop",
            "decision": "decision",
            END: END,
        },
    )

    # discovery → supervisor (CP-2 HITL inside discovery)
    workflow.add_edge("discovery", "supervisor")

    # mini_supervisor → fan-out to [tech_summary, market_eval, competitor]
    # ⚠️ CORRECT: Send는 조건부 엣지 라우터 함수에서 반환해야 함
    def mini_supervisor_router(state: GraphState):
        retry_agents = state.get("retry_agents", [])

        # Judge 재시도: 지정된 에이전트만 재실행
        if retry_agents:
            sends = []
            valid = {"tech_summary", "market_eval", "competitor"}
            for agent in retry_agents:
                if agent in valid:
                    sends.append(Send(agent, state))
            if sends:
                print(f"  Mini-Supervisor: Targeted retry for {retry_agents}")
                return sends

        # 정상 fan-out: 전체 병렬 실행
        print(f"  Mini-Supervisor: Full fan-out for {len(state.get('startup_candidates', []))} candidates")
        return [
            Send("tech_summary", state),
            Send("market_eval", state),
            Send("competitor", state),
        ]

    workflow.add_conditional_edges(
        "mini_supervisor",
        mini_supervisor_router,
        ["tech_summary", "market_eval", "competitor"],
    )

    # 병렬 에이전트 → supervisor (fan-in)
    workflow.add_edge("tech_summary", "supervisor")
    workflow.add_edge("market_eval", "supervisor")
    workflow.add_edge("competitor", "supervisor")

    # judge_loop → supervisor (실패) | decision (통과)
    def judge_router(state: GraphState):
        judge_passed = state.get("judge_passed", False)
        judge_iteration = state.get("judge_iteration", 0)

        if judge_passed:
            return "decision"

        # 재시도 전략에 따라 라우팅
        judge_retry_target = state.get("judge_retry_target", [])
        if judge_retry_target:
            return "supervisor"  # supervisor가 mini_supervisor로 재라우팅

        # 강제 종료 조건
        if judge_iteration >= 3:
            return "decision"

        return "supervisor"

    workflow.add_conditional_edges(
        "judge_loop",
        judge_router,
        {
            "decision": "decision",
            "supervisor": "supervisor",
        },
    )

    # decision → report_gen | supervisor
    def decision_router(state: GraphState):
        investment_decision = state.get("investment_decision")
        iteration_count = state.get("iteration_count", 0)

        # 최대 이터레이션 초과 + hold → 최고점 후보로 보고서 강제 생성 (무한루프 탈출)
        if investment_decision == "hold" and iteration_count >= 10:
            print("  [Decision] 최대 이터레이션 초과 (HOLD) — 최고점 후보로 보고서 강제 생성")
            return "report_gen"
        # hold → supervisor (남은 후보 시도 or 풀 소진 시 재탐색)
        if investment_decision == "hold":
            return "supervisor"
        # CP-4 재검토 요청 시
        if not state.get("judge_passed", False) and investment_decision is None:
            return "supervisor"
        return "report_gen"

    workflow.add_conditional_edges(
        "decision",
        decision_router,
        {
            "report_gen": "report_gen",
            "supervisor": "supervisor",
        },
    )

    # report_gen → END (CP-5 HITL inside report_gen)
    workflow.add_edge("report_gen", END)

    # ── 체크포인터로 컴파일 (HITL 필수) ──
    _schema_classes = [
        ("src.schema.models", "StartupProfile"),
        ("src.schema.models", "TechSummary"),
        ("src.schema.models", "MarketAnalysis"),
        ("src.schema.models", "CompetitorProfile"),
        ("src.schema.models", "ValidationResult"),
        ("src.schema.models", "JudgeVerdict"),
        ("src.schema.models", "HITLRequest"),
        ("src.schema.models", "HITLRecord"),
    ]
    serde = JsonPlusSerializer(allowed_msgpack_modules=_schema_classes)
    checkpointer = MemorySaver(serde=serde)
    return workflow.compile(checkpointer=checkpointer)
