"""
Report Generation Agent - 투자/보류 보고서 생성.

- all_hold: 전부 보류 시 보류 전용 보고서
- 정보 없음 → Tavily 웹검색 보강 → 그래도 없으면 해당 목차 삭제
- PDF 저장
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import GraphState
from src.report.verification import hallucination_check, relevance_check
from src.tools.web_search import web_search
from src.report.pdf_export import md_to_pdf
from src.utils.human_loop import human_approve


def _to_dict(obj: Any) -> dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj) if hasattr(obj, "items") else {}


def _build_constrained_context(state: dict) -> str:
    parts = []
    for name, key in [
        ("startup_candidates", "startup_candidates"),
        ("tech_summaries", "tech_summaries"),
        ("market_analyses", "market_analyses"),
        ("validation_results", "validation_results"),
    ]:
        items = state.get(key) or []
        parts.append(f"## {name}")
        for x in items:
            parts.append(json.dumps(_to_dict(x), ensure_ascii=False, indent=2))
    return "\n".join(parts)


def _fill_via_web_search(section_title: str, startup_name: str, query_hint: str) -> str:
    query = f"{startup_name} {query_hint}"
    return web_search(query, max_results=3)


def _remove_empty_sections(report: str) -> str:
    lines = report.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if (
            "정보 없음" in line
            or "정보없음" in line
            or "데이터 부재" in line
        ) and len(line.strip()) < 50:
            j = len(result) - 1
            while j >= 0:
                if re.match(r"^##\s+", result[j]):
                    result = result[:j]
                    break
                j -= 1
            i += 1
            continue
        result.append(line)
        i += 1
    return "\n".join(result)


REPORT_OUTLINE = """
0. Executive Summary
1. 회사 현황 (1-1~1-8)
2. 투자구조 (2-1~2-4)
3. 재무 현황 및 Bessemer 지표
4. 사업 및 시장 현황 (AI 특화)
5. 매출 및 손익 추정
6. 밸류에이션 및 투자 수익성
7. 종합 투자 검토 의견
8. (별첨) Reference 및 기술 실사 자료
"""

HOLD_REPORT_OUTLINE = """
1. 보류 사유 요약
2. 검토 대상 기업 목록 및 개요
3. 공통 보류 요인
4. 시장/업종 관점 검토
5. 향후 재검토 권고 사항
6. 참고 자료
"""


def _generate_report(
    constrained_context: str,
    question: str,
    target_domain: str,
    startup_name: str,
    feedback: str,
    all_hold: bool,
    llm: ChatOpenAI,
) -> str:
    system = """당신은 AI 스타트업 투자 심사 보고서 작성 전문가입니다.
규칙:
1. 구조화 데이터에 있는 내용만 사용. 추측 금지.
2. 숫자는 데이터에 있을 때만 인용.
3. 각 섹션에 [출처] 표기.
4. Markdown 구조 (##, ###).
5. 투자 보고서 톤: 전문적, 간결."""

    if all_hold:
        outline = HOLD_REPORT_OUTLINE
        extra = "\n전부 투자 보류된 경우의 '보류 보고서'입니다. 검토한 기업들, 공통 보류 요인, 향후 재검토 방안을 서술하세요."
    else:
        outline = REPORT_OUTLINE
        extra = f"\n대상 기업: {startup_name}"

    prompt = f"""질의: {question}
도메인: {target_domain}
{extra}

[구조화 데이터]
{constrained_context[:15000]}

보고서 목차:
{outline}

데이터에 없는 항목은 먼저 "정보 없음"으로 표기하세요. (나중에 웹 검색으로 보강 가능)
{f'[검증 피드백] {feedback}' if feedback else ''}
"""
    try:
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        return resp.content or ""
    except Exception as e:
        return f"# 보고서 생성 오류\n\n{e}"


def _enrich_with_web_search(report: str, startup_name: str) -> str:
    sections = re.split(r"(?=^##\s+)", report, flags=re.MULTILINE)
    result = []
    for block in sections:
        if not block.strip():
            continue
        lines = block.split("\n")
        header = lines[0] if lines else ""
        if "정보 없음" in block or "정보없음" in block or "데이터 부재" in block:
            hint = re.sub(r"^#+\s*", "", header).strip()
            web_text = _fill_via_web_search(header, startup_name, hint)
            if web_text and len(web_text) > 50:
                block = block + f"\n\n[웹 검색 보강]\n{web_text[:1500]}\n"
                result.append(block)
            else:
                continue
        else:
            result.append(block)
    return "\n".join(result).strip()


def _save_report_as_pdf(report: str, startup_name: str, project_root: Path) -> str:
    safe_name = re.sub(r"[^\w\-]", "_", startup_name or "Unknown")[:50]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"report_{safe_name}_{ts}.md"
    md_path.write_text(report, encoding="utf-8")
    pdf_path = reports_dir / f"report_{safe_name}_{ts}.pdf"
    if md_to_pdf(str(md_path), str(pdf_path)):
        return str(pdf_path)
    return str(md_path)


class ReportAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, max_tokens=8000)
        self.max_regenerate = 3
        self.project_root = Path(__file__).resolve().parent.parent.parent

    def __call__(self, state: GraphState) -> dict[str, Any]:
        print("\n>>> [report_gen] 보고서 생성 실행 중...", flush=True)
        human_approve("report_gen", "보고서 생성 진행하시겠습니까?")

        candidates = state.get("startup_candidates") or []
        validations = state.get("validation_results") or []
        question = state.get("question", "")
        target_domain = state.get("target_domain", "Semiconductor AI")
        all_hold = state.get("all_hold", False)

        def _get(o, k, d=None):
            return getattr(o, k, d) if not isinstance(o, dict) else o.get(k, d)

        if not candidates:
            empty = "# 보고서 생성 불가\n\n분석 대상 스타트업이 없습니다."
            path = _save_report_as_pdf(empty, "NoTarget", self.project_root)
            return {
                "final_report": empty,
                "report_file_path": path,
                "report_regeneration_count": 0,
                "is_done": True,
                "all_hold": False,
            }

        best = None
        for v in validations:
            if _get(v, "passed", False) and (best is None or _get(v, "score", 0) > _get(best, "score", 0)):
                best = v
        startup_name = _get(best, "startup_name") or _get(candidates[0], "name", "Unknown")

        if all_hold:
            startup_name = "HoldReport_" + target_domain.replace(" ", "_")

        constrained = _build_constrained_context(state)
        feedback = ""
        regen_count = 0

        for attempt in range(self.max_regenerate + 1):
            report = _generate_report(
                constrained, question, target_domain, startup_name, feedback, all_hold, self.llm
            )
            report = _enrich_with_web_search(report, startup_name)
            report = _remove_empty_sections(report)

            h_result = hallucination_check(report, constrained, self.llm)
            if not h_result.passed:
                regen_count += 1
                feedback = f"(Hallucination) {h_result.reason}. {h_result.details}"
                print(f"   [report_gen] 검증 실패 (시도 {attempt + 1}/{self.max_regenerate + 1})", flush=True)
                if attempt < self.max_regenerate:
                    continue
                report += f"\n\n---\n*검증 경고: {feedback}*\n"
                break

            r_result = relevance_check(report, question, target_domain, self.llm)
            if not r_result.passed:
                regen_count += 1
                feedback = f"(Relevance) {r_result.reason}"
                print(f"   [report_gen] 관련성 검증 실패 (시도 {attempt + 1})", flush=True)
                if attempt < self.max_regenerate:
                    continue
                break
            feedback = ""
            break

        path = _save_report_as_pdf(report, startup_name, self.project_root)
        print(f"   [report_gen] 보고서 저장: {path}", flush=True)
        print(f"   [report_gen] 재생성 시도: {regen_count}회", flush=True)

        return {
            "final_report": report,
            "report_file_path": path,
            "report_regeneration_count": regen_count,
            "is_done": True,
            "all_hold": all_hold,
        }
