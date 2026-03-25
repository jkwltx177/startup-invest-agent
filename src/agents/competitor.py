from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from src.graph.state import GraphState
from src.schema.models import CompetitorProfile
from src.tools.retriever import SemiconductorRetriever
from src.tools.web_search import TavilyWebSearch
from src.tools.tool_router import ToolRouter
from src.tools.token_utils import trim_list_context, trim_candidates_str


class CompetitorProfileList(BaseModel):
    competitors: List[CompetitorProfile] = Field(
        description="List of competitor profiles (up to 2 per startup)"
    )


_CROSS_STARTUP_PROMPT = """당신은 반도체 AI 스타트업 비교 분석 전문가입니다.
아래 컨텍스트를 참고하여 후보 스타트업들을 서로 비교 분석하세요.

[컨텍스트]
{context}

[후보 스타트업 목록]
{candidates}

[비교 쌍 (startup_name → competitor_name)]
{comparison_pairs}

규칙:
- competitor_name 은 반드시 위 [후보 스타트업 목록]에 있는 이름만 사용하세요.
- 대기업(NVIDIA, SK, Intel, Qualcomm 등)은 competitor_name 으로 사용하지 마세요.
- 각 비교 쌍에 대해 tech_gap_summary, market_share_pct, funding_total_usd, strategic_partners 를 채우세요.
- 정보가 불확실하면 market_share_pct=0, funding_total_usd=0 으로 두세요.
"""

_COMPETITOR_PROMPT = """당신은 반도체 AI 경쟁 분석 전문가입니다.
아래 컨텍스트를 기반으로 각 스타트업의 주요 경쟁사를 분석하세요.

[컨텍스트]
{context}

[분석 대상 스타트업]
{candidates}

각 스타트업당 최대 2개의 경쟁사를 식별하여 다음을 분석하세요:
- startup_name: 분석 대상 스타트업 이름
- competitor_name: 경쟁사 이름
- tech_gap_summary: 스타트업과 경쟁사 간 기술 격차 요약
- market_share_pct: 경쟁사 시장 점유율 추정 (%)
- funding_total_usd: 경쟁사 총 자금 조달액 (USD, 알 수 없으면 0)
- strategic_partners: 경쟁사 주요 전략적 파트너 목록
- source_urls: 정보 출처 URL
"""


class CompetitorAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(CompetitorProfileList, method="function_calling")
        self.retriever = SemiconductorRetriever()
        self.web_search = TavilyWebSearch()
        self.tool_router = ToolRouter()

    def __call__(self, state: GraphState) -> dict:
        print("◆ [경쟁사 분석 에이전트]")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {
                "competitor_profiles": [],
                "logs": ["[Competitor] No candidates to analyze."],
            }

        agent_queries = state.get("agent_queries", {})
        _question = agent_queries.get("competitor", state.get("question", ""))

        # Tool Router로 툴 결정
        tools = self.tool_router.decide("competitor", state)

        all_context_parts = []
        all_sources = []

        # Vector 검색 (상위 3개 후보, k=3)
        if "vector" in tools:
            for c in candidates[:3]:
                if len(candidates) >= 2:
                    query = f"{c.name} {c.domain} technology product funding startup"
                else:
                    query = f"{c.name} {c.domain} competitor alternative company semiconductor"
                docs, _ = self.retriever.retrieve_with_cache_check(query, k=3)
                for d in docs:
                    src = d.metadata.get("source", "Unknown")
                    all_context_parts.append(f"[Vector: {src}]\n{d.page_content[:500]}")
                    if src not in all_sources:
                        all_sources.append(src)

        # 웹 검색 (상위 3개 후보, 결과 2건씩)
        if "web" in tools:
            print("  경쟁사 데이터 웹 검색 중")
            for c in candidates[:3]:
                if len(candidates) >= 2:
                    web_query = f"{c.name} {c.domain} technology funding product 2025"
                else:
                    web_query = f"{c.name} {c.domain} competitors semiconductor AI rival 2025"
                web_ctx, web_urls = self.web_search.get_context(web_query, max_results=2)
                if web_ctx:
                    all_context_parts.append(web_ctx)
                    all_sources.extend(u for u in web_urls if u not in all_sources)

        context = trim_list_context(all_context_parts, max_total_chars=4000)
        candidate_list = trim_candidates_str(candidates, max_per=100)

        if len(candidates) >= 2:
            pairs = []
            for c in candidates:
                others = [o.name for o in candidates if o.name != c.name]
                pairs.append(f"- {c.name} → {', '.join(others)}")
            comparison_pairs_str = "\n".join(pairs)

            prompt = _CROSS_STARTUP_PROMPT.format(
                context=context or "(컨텍스트 없음)",
                candidates=candidate_list,
                comparison_pairs=comparison_pairs_str,
            )
        else:
            prompt = _COMPETITOR_PROMPT.format(
                context=context or "(컨텍스트 없음)",
                candidates=candidate_list,
            )

        try:
            result = self.structured_llm.invoke(prompt)
            competitor_profiles = result.competitors if result else []
            # N>=2: competitor_name이 후보 목록 밖이면 제거 (대기업 등 필터)
            if len(candidates) >= 2:
                candidate_names = {c.name for c in candidates}
                before = len(competitor_profiles)
                competitor_profiles = [
                    cp for cp in competitor_profiles
                    if cp.competitor_name in candidate_names
                ]
                removed = before - len(competitor_profiles)
                if removed:
                    print(f"  [필터] 후보 외 경쟁사 {removed}건 제거됨")
            # source_urls 보강
            for cp in competitor_profiles:
                if not cp.source_urls:
                    cp.source_urls = all_sources[:3]
                if not cp.vector_doc_ids:
                    cp.vector_doc_ids = [s for s in all_sources if not s.startswith("http")]
        except Exception as e:
            print(f"  구조화 출력 오류: {e}")
            competitor_profiles = []

        return {
            "competitor_profiles": competitor_profiles,
            "logs": [f"[Competitor] Found {len(competitor_profiles)} competitor profiles."],
        }
