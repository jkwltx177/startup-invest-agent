"""
Supervisor — 순차 평가 라우팅 + Scorecard 기준은 decision 에서 수행.

흐름:
- 후보 없음 → discovery
- 후보 있음 → Rank (candidate_eval_index+1)/N 대상으로 tech→market→competitor→decision
- decision 이후 라우팅은 workflow 의 conditional 에서 처리
"""
from src.graph.state import GraphState


class Supervisor:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name

    def __call__(self, state: GraphState) -> dict:
        candidates = state.get("startup_candidates") or []
        idx = int(state.get("candidate_eval_index", 0) or 0)

        print("\n>>> [supervisor] 오케스트레이션 (Scorecard 60% + Semi 25% + Trend 15%, Gate 후 가중합)", flush=True)

        if not candidates:
            print("   → 후보 없음: discovery", flush=True)
            return {"next_agent": "discovery"}

        if idx >= len(candidates):
            print("   → 순차 평가 종료 (전원 보류 경로): report_gen", flush=True)
            return {"next_agent": "report_gen", "all_hold": True}

        target = candidates[idx]
        print(
            f"   → 순차 평가: 상위 {len(candidates)}개 중 Rank {idx + 1}/{len(candidates)} — {target.name}",
            flush=True,
        )

        return {
            "next_agent": "tech_summary",
            "evaluation_target_name": target.name,
        }
