from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.tools.tool_router import ToolRouter


class Supervisor:
    """
    역할 1: 라우팅 — next_agent 결정
    역할 2: 쿼리 재작성 — ToolRouter.rewrite_query()로 agent_queries 구성
    """

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name)
        self.tool_router = ToolRouter()

    def __call__(self, state: GraphState) -> dict:
        current_iter = state.get("iteration_count", 0)
        print(f"◆ [슈퍼바이저] (이터레이션: {current_iter})")

        # 무한 루프 방지 → decision 경유 (투자 결정은 반드시 실행)
        pool = state.get("candidate_pool", [])
        if current_iter >= 10:
            print("  최대 이터레이션 도달 — 투자 결정 강제 진행")
            return {
                "next_agent": "decision",
                "judge_passed": True,   # judge_loop 재진입 방지
                "pool_offset": len(pool),  # pool 소진 → decision_router가 supervisor 재진입 방지
                "iteration_count": current_iter + 1,
                "logs": ["[Supervisor] Max iterations reached. Forcing decision node."],
            }

        question = state.get("question", "")
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])
        competitor_profiles = state.get("competitor_profiles", [])
        judge_passed = state.get("judge_passed", False)
        judge_iteration = state.get("judge_iteration", 0)
        judge_retry_target = state.get("judge_retry_target", [])
        investment_decision = state.get("investment_decision")
        pool_offset = state.get("pool_offset", 0)

        # ── 라우팅 로직 ──

        # 0-a. Hold + 풀 소진 → 후보 초기화 후 discovery 재탐색
        if investment_decision == "hold" and pool_offset >= len(pool) and len(pool) > 0:
            print(f"  HOLD (풀 소진 {pool_offset}/{len(pool)}) → 후보 재탐색")
            agent_queries = self._build_agent_queries(question, state)
            return {
                "startup_candidates": [],
                "candidate_pool": [],
                "pool_offset": 0,
                "investment_decision": None,
                "judge_passed": False,
                "judge_iteration": 0,
                "judge_retry_target": [],
                "retry_agents": [],
                "next_agent": "discovery",
                "iteration_count": current_iter + 1,
                "agent_queries": {**state.get("agent_queries", {}), **agent_queries},
                "logs": [f"[Supervisor] 풀 소진 (all HOLD) → discovery 재탐색 (iteration {current_iter + 1})"],
            }

        # 0-b. Hold + 남은 후보 → 다음 후보로 교체 후 mini_supervisor
        if investment_decision == "hold" and pool_offset < len(pool):
            next_c = pool[pool_offset]
            print(f"  보류 처리 → 다음 후보: {next_c.name}")
            agent_queries = self._build_agent_queries(question, state)
            return {
                "startup_candidates": [next_c],
                "pool_offset": pool_offset + 1,
                "investment_decision": None,
                "judge_passed": False,
                "judge_iteration": 0,
                "judge_retry_target": [],
                "retry_agents": [],
                "next_agent": "mini_supervisor",
                "iteration_count": current_iter + 1,
                "agent_queries": {**state.get("agent_queries", {}), **agent_queries},
                "logs": [f"[Supervisor] Switching candidate → {next_c.name} (pool {pool_offset + 1}/{len(pool)})"],
            }

        # 1. Discovery 미완료 → discovery
        if not candidates:
            agent_queries = self._build_agent_queries(question, state)
            return {
                "next_agent": "discovery",
                "iteration_count": current_iter + 1,
                "agent_queries": {**state.get("agent_queries", {}), **agent_queries},
                "logs": [f"[Supervisor] Routing to discovery (iteration {current_iter + 1})"],
            }

        # 2. Judge 실패 후 재시도 대상 에이전트 있음 → mini_supervisor (재실행)
        if judge_retry_target and not judge_passed:
            print(f"  판정 재시도 요청: {judge_retry_target}")
            agent_queries = self._build_agent_queries(question, state)
            return {
                "next_agent": "mini_supervisor",
                "iteration_count": current_iter + 1,
                "agent_queries": {**state.get("agent_queries", {}), **agent_queries},
                "retry_agents": judge_retry_target,   # mini_supervisor_router가 읽는 중계 필드
                "judge_retry_target": [],             # 소비 완료
                "logs": [f"[Supervisor] Routing to mini_supervisor for retry: {judge_retry_target}"],
            }

        # 3. 분석 미완료 → mini_supervisor (병렬 fan-out)
        current_names = {c.name for c in candidates}
        has_tech = any(ts.startup_name in current_names for ts in tech_summaries)
        has_market = any(ma.startup_name in current_names for ma in market_analyses)
        has_competitor = len(competitor_profiles) >= len(candidates) * 2  # 후보당 최대 2개
        analysis_done = has_tech and has_market

        if not analysis_done:
            agent_queries = self._build_agent_queries(question, state)
            return {
                "next_agent": "mini_supervisor",
                "iteration_count": current_iter + 1,
                "agent_queries": {**state.get("agent_queries", {}), **agent_queries},
                "logs": [
                    f"[Supervisor] Routing to mini_supervisor. "
                    f"tech={has_tech}, market={has_market}, competitor={has_competitor}"
                ],
            }

        # 4. 분석 완료, Judge 미통과 → judge_loop
        if not judge_passed and judge_iteration < 3:
            return {
                "next_agent": "judge_loop",
                "iteration_count": current_iter + 1,
                "logs": [f"[Supervisor] Routing to judge_loop (judge_iteration={judge_iteration})"],
            }

        # 5. Judge 통과 또는 max iter → decision
        return {
            "next_agent": "decision",
            "iteration_count": current_iter + 1,
            "logs": [
                f"[Supervisor] Routing to decision. "
                f"judge_passed={judge_passed}, judge_iteration={judge_iteration}"
            ],
        }

    def _build_agent_queries(self, question: str, state: GraphState) -> dict:
        """에이전트별 쿼리 재작성"""
        candidates = state.get("startup_candidates", [])
        queries = {}
        for agent_name in ("discovery", "tech_summary", "market_eval", "competitor"):
            try:
                queries[agent_name] = self.tool_router.rewrite_query(
                    agent_name, question, candidates=candidates
                )
            except Exception as e:
                print(f"  쿼리 재작성 오류 ({agent_name}): {e}")
                queries[agent_name] = question
        return queries
