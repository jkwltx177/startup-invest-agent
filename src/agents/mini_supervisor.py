from src.graph.state import GraphState


class MiniSupervisor:
    """
    병렬 fan-out 조율 노드.
    실제 fan-out은 workflow.py의 라우터 함수에서 Send를 사용하여 처리.
    이 노드 자체는 pass-through (빈 반환).
    """

    def __call__(self, state: GraphState) -> dict:
        print("◆ [미니 슈퍼바이저]")
        candidates = state.get("startup_candidates", [])
        judge_retry_target = state.get("judge_retry_target", [])

        if judge_retry_target:
            print(f"  재시도 대상: {judge_retry_target}")
        else:
            print(f"  전체 분석 시작 ({len(candidates)}개 후보)")

        return {}
