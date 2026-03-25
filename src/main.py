import asyncio
import logging
import warnings
from uuid import uuid4
from dotenv import load_dotenv
from langgraph.types import Command

warnings.filterwarnings("ignore", message="Deserializing unregistered type")


class _SuppressMsgpackLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "Deserializing unregistered type" not in record.getMessage()


logging.getLogger().addFilter(_SuppressMsgpackLog())

from src.graph.workflow import create_workflow

load_dotenv()

_INITIAL_STATE_TEMPLATE = {
    "target_domain": "반도체 AI",
    "route_type": "pipeline",
    "detected_domain": "",
    "direct_answer": None,
    "next_agent": "",
    "agent_queries": {},
    "startup_candidates": [],
    "candidate_pool": [],
    "pool_offset": 0,
    "validation_results": [],
    "tech_summaries": [],
    "market_analyses": [],
    "competitor_profiles": [],
    "judge_history": [],
    "mini_judge_history": [],
    "judge_iteration": 0,
    "judge_passed": False,
    "judge_retry_target": [],
    "retry_agents": [],
    "iteration_count": 0,
    "is_done": False,
    "hitl_enabled": True,
    "hitl_records": [],
    "investment_decision": None,
    "selected_startup": None,
    "final_report": None,
    "report_pdf_path": None,
    "logs": [],
}


async def run_pipeline(app, question: str):
    """단일 파이프라인 실행 (초기 상태 리셋 + 새 thread_id)"""
    initial_state = {**_INITIAL_STATE_TEMPLATE, "question": question}
    thread = {"configurable": {"thread_id": str(uuid4())}}
    input_data = initial_state

    print(f"\n[파이프라인 시작]")
    print(f"질의: {question}\n")

    # HITL 인터랙션 루프
    while True:
        try:
            result = await app.ainvoke(input_data, thread)
        except Exception as e:
            print(f"\n[오류] 파이프라인 실행 중 오류 발생: {e}")
            raise

        # HITL 인터럽트 처리
        if "__interrupt__" in result:
            interrupts = result["__interrupt__"]
            for interrupt_obj in interrupts:
                cp = interrupt_obj.value if hasattr(interrupt_obj, "value") else interrupt_obj
                checkpoint_id = cp.get("checkpoint_id", "Unknown")
                message = cp.get("message", "")
                options = cp.get("options", [])
                is_blocking = cp.get("is_blocking", True)

                print(f"\n{'='*60}")
                print(f"[HITL {checkpoint_id}]")
                print(message)

                if not is_blocking:
                    # Non-blocking: 자동 확인
                    print(f"(Non-blocking checkpoint — 자동 확인)")
                    user_input = options[0] if options else "확인"
                else:
                    # Blocking: 사용자 입력 대기
                    if options:
                        print("\n선택지:")
                        for i, opt in enumerate(options, 1):
                            print(f"  {i}. {opt}")
                        print()
                    user_input = input("응답 (번호 또는 직접 입력): ").strip()
                    # 번호 입력 처리
                    if user_input.isdigit():
                        idx = int(user_input) - 1
                        if 0 <= idx < len(options):
                            user_input = options[idx]
                    print(f"→ 선택: {user_input}")

                input_data = Command(resume=user_input)
            continue  # 다음 라운드 실행

        # 파이프라인 완료
        break

    # 최종 결과 출력
    print("\n" + "=" * 60)
    print("  파이프라인 완료")
    print("=" * 60)

    # Direct 응답
    if result.get("route_type") == "direct":
        print(f"\n[직접 응답]\n{result.get('direct_answer', '')}")
        return result

    # 스코어카드 요약
    validation_results = result.get("validation_results", [])
    if validation_results:
        print("\n[투자 스코어카드 요약]")
        for res in validation_results:
            status_icon = {"invest": "✅", "additional_review": "🔍", "hold": "❌"}.get(
                res.investment_category, "❓"
            )
            print(f"{status_icon} {res.startup_name}: {res.score:.0f}점 [{res.investment_category.upper()}]")
            print(f"   근거: {res.reason[:120]}...")

    # 전체 결정
    investment_decision = result.get("investment_decision", "unknown")
    selected_startup = result.get("selected_startup", "N/A")
    print(f"\n[최종 투자 결정] {(investment_decision or 'unknown').upper()}")
    print(f"[선정 스타트업] {selected_startup}")

    # PDF 보고서 경로
    pdf_path = result.get("report_pdf_path")
    if pdf_path:
        print(f"\n[PDF 보고서] {pdf_path}")
    elif not result.get("final_report"):
        print("\n(보고서 생성되지 않음)")

    return result


async def main():
    print("\n" + "=" * 60)
    print("  반도체 AI 스타트업 투자 평가 에이전트")
    print("  (종료: 'exit' 또는 빈 입력)")
    print("=" * 60)

    # 워크플로우 한 번만 생성 → FAISS 인덱스 메모리 상주
    app = create_workflow()

    while True:
        question = input("\n[질의] 분석할 반도체 AI 스타트업 / 도메인을 입력하세요\n> ").strip()
        if not question or question.lower() in ("exit", "quit", "종료", "q"):
            print("에이전트를 종료합니다.")
            break

        await run_pipeline(app, question)
        print("\n" + "=" * 60)
        print("다음 질의를 입력하거나 'exit'를 입력해 종료하세요.")


if __name__ == "__main__":
    asyncio.run(main())
