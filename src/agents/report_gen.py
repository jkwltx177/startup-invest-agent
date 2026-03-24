"""
Report Generation Agent - 투자/보류 보고서 생성.

- 순서 고정: SUMMARY → 목차 → 본문 → REFERENCE
- 본문에 Markdown 표(비교·재무·리스크 등) 허용, 자료 부족 시 검토용 가정·시나리오로 보완 가능
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
from src.tools.web_search import web_search_structured, format_web_items_for_prompt
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


def _gather_web_auxiliary(startup_name: str, target_domain: str, all_hold: bool) -> tuple[str, str]:
    """
    보고서 작성 보조용 웹 맥락 + 검증용 통합 문자열.
    Returns: (prompt_block, combined_for_verification_appendix)
    """
    if all_hold:
        queries = [
            f"{target_domain} semiconductor startup investment trends outlook",
            f"{target_domain} venture investment hold criteria",
        ]
    else:
        queries = [
            f"{startup_name} company semiconductor AI startup overview",
            f"{startup_name} funding technology product",
            f"{target_domain} TAM market CAGR semiconductor AI",
        ]
    seen: set[str] = set()
    all_items: list[dict] = []
    for q in queries:
        for it in web_search_structured(q, max_results=3):
            u = it.get("url") or ""
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            all_items.append(it)
            if len(all_items) >= 12:
                break
        if len(all_items) >= 12:
            break

    block = format_web_items_for_prompt(all_items)
    if not block:
        return "", ""

    prompt_block = (
        "아래는 Tavily 웹 검색으로 수집한 보조 맥락이다. "
        "구조화 데이터가 비어 있거나 부족한 항목은 이 맥락과 일반적 투자 검토 관행을 바탕으로 서술·표로 정리하라. "
        "구체 수치는 맥락에 있을 때만 단정하고, 없으면 가정·시나리오 표로 쓰되 표 하단에 ※로 구분하라.\n\n"
        + block
    )
    return prompt_block, "\n\n## 웹 검색 보조 맥락(검증용)\n" + block


REPORT_BODY_OUTLINE = """
1. 회사 현황 (사업·제품·기술·조직 등, 하위 항목은 자료에 맞게 번호 매김)
2. 투자 구조 및 지분 관계
3. 재무 현황 및 Bessemer 지표 (자료 있을 때만)
4. 사업 및 시장 현황 (반도체·AI 맥락)
5. 매출 및 손익 추정 (근거 있을 때만)
6. 밸류에이션 및 투자 수익성 (근거 있을 때만)
7. 종합 투자 검토 의견
"""

HOLD_BODY_OUTLINE = """
1. 보류 사유 요약
2. 검토 대상 기업 목록 및 개요
3. 공통 보류 요인
4. 시장·업종 관점 검토
5. 향후 재검토 권고 사항
"""

REFERENCE_FORMAT = """
REFERENCE 섹션은 반드시 아래 형식만 사용한다. 실제로 본문·SUMMARY 작성에 활용한 출처만 넣는다.

### 기관 보고서
- 발행기관(YYYY). *보고서명*. URL

### 학술 논문
- 저자(YYYY). 논문제목. *학술지명*, 권(호), 페이지.

### 웹페이지
- 기관명 또는 작성자(YYYY-MM-DD). *제목*. 사이트명, URL

구조화 데이터의 PDF/문서 메타데이터(Source, 페이지)는 '기관 보고서' 또는 '웹페이지'로 적절히 분류해 넣는다.
웹 보조자료는 위 웹페이지 형식으로만 REFERENCE에 넣는다.
표·가정으로 보완한 항목도 근거가 된 자료를 REFERENCE에 포함한다.
"""


SYSTEM_REPORT = f"""당신은 한국어 투자 심사 보고서를 작성하는 전문가다. 문서는 **기관용 투자검토 보고서**처럼 정돈된 레이아웃과 가독성을 갖춘다.

[문서 대제목 — 반드시 맨 위에 한 줄]
- 문서 **가장 첫 줄**은 보고서 전체를 대표하는 **큰 제목**만 온다. Markdown 1단계 제목 1개: `# …`
- 투자 검토 건: `# [대상기업명] 투자 검토 보고서` 형태를 권장한다. 기업명이 불명확하면 `# 반도체·AI 분야 투자 검토 보고서` 등으로 쓴다.
- 보류 통합 보고서: `# [도메인] 투자 검토 종합 보고서 (보류)` 등으로 쓴다.
- 대제목 바로 아래(선택): 한 칸 띄우고 **한두 줄** 메타만 쓴다. 예: `**검토 도메인:** …` / `**작성 목적:** …` — H1(`#`)은 대제목에만 쓰고 여기서는 굵게 표기만 한다.

[본문 섹션 순서 — 대제목·메타 다음부터, 제목 철자 고정]
1. `# SUMMARY`
2. `# 목차`
3. 본문: `# 1.`, `# 2.` … 형태의 절만 사용 (필요 시 절 아래 `##` 소제목)
4. `# REFERENCE` (항상 마지막 최상위 섹션)

[SUMMARY]
- 투자 의사결정자가 3분 안에 읽을 수 있는 핵심 요약. 완전한 문장 위주, A4 기준 반 페이지 이내.
- 필요하면 **핵심 지표·투자 포인트만** 담은 Markdown 표 1개까지 허용(행·열 남발 금지).

[목차]
- `# 목차` 아래에 본문에 실제로 등장할 절 제목을 **작성 순서와 동일하게** bullet 로 나열한다 (예: `- 1. 회사 현황`, `- 2. …`).
- 문서 맨 위 **대제목·SUMMARY·목차·REFERENCE** 항목은 목차 bullet 에 넣지 않는다.

[본문]
- 전문 투자 보고서 문체. 절마다 서술 + **필요 시 Markdown 표**를 넣는다.
- 표 활용 예: 회사·사업 개요, 주주/지분 스냅샷, 재무·지표 하이라이트, 시장·경쟁 비교, 리스크·완화 요약, 시나리오별 민감도 등.
- 자료가 부족하면 표·문장으로 **검토용 가정·시나리오**를 채워 넣되, 해당 표 또는 절 바로 아래에 `※ 일부 항목은 내부 검토용 가정·추정이며, 공개 실적과 다를 수 있음.` 등 **한 줄 이상**으로 구분한다.
- JSON·Python dict·코드 블록·`[보조자료 N]`·원시 URL 나열을 본문에 넣지 않는다.
- 인라인 URL·각주·"[출처]"는 본문·SUMMARY에 넣지 않는다.

[REFERENCE]
- 문서 **맨 끝**에 `# REFERENCE` 한 번만 두고, {REFERENCE_FORMAT}
"""


def _generate_report(
    constrained_context: str,
    web_prompt_block: str,
    question: str,
    target_domain: str,
    startup_name: str,
    feedback: str,
    all_hold: bool,
    llm: ChatOpenAI,
) -> str:
    if all_hold:
        body_outline = HOLD_BODY_OUTLINE
        extra = (
            "이 보고서는 검토한 모든 후보가 보류된 경우의 '보류 보고서'다. "
            "SUMMARY에서 보류 개요와 공통 시사점을 요약한다.\n"
            f"문서 대제목 예: `# {target_domain} 반도체·AI 투자 검토 종합 보고서 (보류)`"
        )
    else:
        body_outline = REPORT_BODY_OUTLINE
        extra = (
            f"대상 기업명: {startup_name}\n"
            f"문서 대제목 예: `# {startup_name} 투자 검토 보고서` (기업명은 필요 시 정리)"
        )

    user = f"""질의: {question}
도메인: {target_domain}
{extra}

[내부 구조화 데이터 — 최우선 근거]
{constrained_context[:18000]}

{web_prompt_block if web_prompt_block else "[웹 보조 맥락 없음 — 내부 데이터와 일반적 투자 검토 틀로만 서술]"}

[작성할 본문 절 가이드(자료 없는 절은 생략)]
{body_outline}

{f'[이전 시도 검증 피드백 — 반영해 수정]\n{feedback}' if feedback else ''}

위 순서(문서 대제목 → SUMMARY → 목차 → 본문 → REFERENCE)와 형식을 지키는 단일 Markdown 보고서만 출력하라.
"""
    try:
        resp = llm.invoke([SystemMessage(content=SYSTEM_REPORT), HumanMessage(content=user)])
        return (resp.content or "").strip()
    except Exception as e:
        return f"# 보고서 생성 오류\n\n{e}"


def _strip_garbage(report: str) -> str:
    """원시 dict/코드펜스 등 흔한 오염 제거."""
    out = report
    if "```" in out:
        out = re.sub(r"```(?:json|python)?\s*[\s\S]*?```", "", out)
    return out.strip()


def _normalize_report_start(report: str) -> str:
    """`# SUMMARY` 앞에 문서 대제목(`# …` 첫 줄)이 있으면 유지. 그 앞 잡문자만 제거."""
    r = report.strip()
    if not r or "# SUMMARY" not in r:
        return r
    if r.startswith("# SUMMARY"):
        return r
    idx = r.find("# SUMMARY")
    head = r[:idx].strip()
    first_line = head.split("\n", 1)[0].strip() if head else ""
    if first_line.startswith("# ") and first_line != "# SUMMARY":
        return r
    if idx > 0:
        return r[idx:].strip()
    return r


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
        self.llm = ChatOpenAI(model=model_name, max_tokens=12000, temperature=0.35)
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
        startup_name = (
            state.get("selected_startup")
            or _get(best, "startup_name")
            or _get(candidates[0], "name", "Unknown")
        )

        if all_hold:
            startup_name = "HoldReport_" + target_domain.replace(" ", "_")

        constrained = _build_constrained_context(state)
        web_block, web_for_verify = _gather_web_auxiliary(startup_name, target_domain, all_hold)
        combined_for_hallucination = constrained + (web_for_verify or "")

        feedback = ""
        regen_count = 0
        report = ""

        for attempt in range(self.max_regenerate + 1):
            report = _generate_report(
                constrained,
                web_block,
                question,
                target_domain,
                startup_name,
                feedback,
                all_hold,
                self.llm,
            )
            report = _normalize_report_start(_strip_garbage(report))

            h_result = hallucination_check(report, combined_for_hallucination, self.llm)
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
