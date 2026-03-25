from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from src.graph.state import GraphState
from src.schema.models import TechSummary
from src.tools.retriever import SemiconductorRetriever
from src.tools.web_search import TavilyWebSearch
from src.tools.tool_router import ToolRouter
from src.tools.token_utils import trim_context, trim_list_context, trim_candidates_str


class TechSummaryList(BaseModel):
    summaries: List[TechSummary] = Field(description="List of technical summaries for each candidate")


_TECH_PROMPT = """당신은 반도체 AI 기술 분석 전문가입니다.
아래 컨텍스트를 기반으로 각 스타트업의 핵심 기술을 분석하세요.

[컨텍스트]
{context}

[분석 대상 스타트업]
{candidates}

각 스타트업에 대해 다음을 분석하세요:
- tech_type: 핵심 기술 카테고리 (예: AI 추론 칩, HBM 컨트롤러, EDA 자동화)
- core_mechanism: 핵심 기술 메커니즘 또는 알고리즘
- application_area: 반도체 분야 주요 응용 영역
- differentiation: 기존 솔루션 대비 기술적 혁신/개선점
- strengths: 기술적 강점 목록
- weaknesses: 기술적 약점 목록
- sources: 분석에 사용된 소스 URL
- confidence_score: 분석 신뢰도 (0-1)
"""


class TechSummaryAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(TechSummaryList, method="function_calling")
        self.retriever = SemiconductorRetriever()
        self.web_search = TavilyWebSearch()
        self.tool_router = ToolRouter()

    def __call__(self, state: GraphState) -> dict:
        print("◆ [기술 요약 에이전트]")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"tech_summaries": [], "logs": ["[TechSummary] No candidates to analyze."]}

        agent_queries = state.get("agent_queries", {})
        question = agent_queries.get("tech_summary", state.get("question", ""))
        if not question:
            question = " ".join([f"{c.name} {c.domain} technology" for c in candidates])

        # 캐시 HIT 체크 (k=5로 축소)
        tech_query = f"semiconductor technology analysis {question}"
        docs, cache_hit = self.retriever.retrieve_with_cache_check(tech_query, k=5)

        all_context_parts = []
        all_sources = []

        # Vector context (청크당 600자 트리밍)
        if docs:
            for d in docs:
                src = d.metadata.get("source", "Unknown")
                all_context_parts.append(f"[Vector: {src}]\n{d.page_content[:600]}")
                if src not in all_sources:
                    all_sources.append(src)

        # Cache MISS → 웹 검색 보완 (상위 2개 후보, 검색결과 2건)
        if not cache_hit:
            print("  캐시 미스 — 웹 검색 보완")
            for c in candidates[:2]:
                web_query = f"{c.name} {c.domain} semiconductor technology 2025"
                web_ctx, web_urls = self.web_search.get_context(web_query, max_results=2)
                if web_ctx:
                    all_context_parts.append(web_ctx)
                    all_sources.extend(u for u in web_urls if u not in all_sources)

        context = trim_list_context(all_context_parts, max_total_chars=4000)
        candidates_str = trim_candidates_str(candidates, max_per=100)

        prompt = _TECH_PROMPT.format(
            context=context or "(컨텍스트 없음)",
            candidates=candidates_str,
        )

        try:
            result = self.structured_llm.invoke(prompt)
            tech_summaries = result.summaries if result else []
            # sources 필드 보강
            for ts in tech_summaries:
                if not ts.sources:
                    ts.sources = all_sources[:3]
                if ts.confidence_score == 0.0:
                    ts.confidence_score = 0.75 if cache_hit else 0.55
        except Exception as e:
            print(f"  구조화 출력 오류: {e}")
            tech_summaries = []

        log_msg = (
            f"[TechSummary] Analyzed {len(tech_summaries)} summaries. "
            f"cache_hit={cache_hit}"
        )
        return {
            "tech_summaries": tech_summaries,
            "_cache_hit_flags": {**state.get("_cache_hit_flags", {}), "tech_summary": cache_hit},
            "logs": [log_msg],
        }
