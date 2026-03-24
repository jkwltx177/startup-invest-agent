#!/usr/bin/env python3
"""
전체 Agentic RAG 파이프라인 실행.

질의 입력 → Supervisor → Discovery → Tech/Market/Competitor → Decision → Report

실행: uv run python scripts/run_full.py
      (프롬프트에서 질의 입력, Enter 시 기본값)

      uv run python scripts/run_full.py "질의 내용"
      (인자로 질의 전달)
"""
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
os.chdir(_root)

from dotenv import load_dotenv

load_dotenv()

# huggingface_hub는 HF_TOKEN 사용. HUGGINGFACEHUB_API_TOKEN 있으면 자동 매핑
if not os.environ.get("HF_TOKEN") and os.environ.get("HUGGINGFACEHUB_API_TOKEN"):
    os.environ["HF_TOKEN"] = os.environ["HUGGINGFACEHUB_API_TOKEN"]

if not os.environ.get("OPENAI_API_KEY"):
    print("경고: OPENAI_API_KEY가 .env에 없습니다. 환경변수를 확인하세요.")


def main():
    import asyncio
    from src.graph.workflow import create_workflow

    default_question = "AI chip, NPU 관련 투자 후보 스타트업 추천"
    print("=" * 60)
    print("AI 스타트업 투자 분석 파이프라인")
    print("=" * 60)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        q = input("질의 입력 (Enter=기본값): ").strip()
        question = q if q else default_question

    target_domain = "Semiconductor AI"
    print(f"\n질의: {question}")
    print(f"도메인: {target_domain}\n")

    workflow = create_workflow()
    state = {
        "question": question,
        "target_domain": target_domain,
        "iteration_count": 0,
        "startup_candidates": [],
        "tech_summaries": [],
        "market_analyses": [],
        "validation_results": [],
        "judge_history": [],
        "is_done": False,
        "all_hold": False,
    }
    config = {"configurable": {"thread_id": "run-full-1"}}

    async def run():
        # astream으로 1회 실행 + 각 노드 완료 시 진행 출력
        final_state = dict(state)
        async for event in workflow.astream(state, config):
            for node_name, node_output in event.items():
                print(f"\n>>> [{node_name}] 완료", flush=True)
                if isinstance(node_output, dict):
                    for k, v in node_output.items():
                        if k in final_state and isinstance(final_state.get(k), list) and isinstance(v, list):
                            final_state[k] = list(final_state[k]) + v
                        else:
                            final_state[k] = v
        return final_state

    result = asyncio.run(run())

    print("\n--- 결과 ---")
    candidates = result.get("startup_candidates", [])
    print(f"후보: {len(candidates)}건")
    for c in (candidates or [])[:5]:
        print(f"  - {c.name if hasattr(c, 'name') else c} ({getattr(c, 'domain', '')})")

    report = result.get("final_report")
    report_path = result.get("report_file_path")
    regen_count = result.get("report_regeneration_count", 0)
    all_hold = result.get("all_hold", False)

    if all_hold:
        print("(전부 보류 → 보류 보고서 생성됨)")
    if report_path:
        print(f"\n보고서 저장: {report_path}")
    if regen_count > 0:
        print(f"보고서 재생성 시도: {regen_count}회")
    if report:
        print(f"\n보고서 미리보기:\n{report[:300]}...")
    print("\n=== 완료 ===")


if __name__ == "__main__":
    main()
