from typing import List
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from src.graph.state import GraphState
from src.schema.models import StartupProfile
from src.tools.retriever import SemiconductorRetriever
from src.tools.web_search import TavilyWebSearch
from src.tools.tool_router import ToolRouter
from src.tools.token_utils import trim_context, trim_list_context


class StartupList(BaseModel):
    candidates: List[StartupProfile] = Field(description="List of identified semiconductor AI startups")


# 반도체 Value Chain 기반 서브쿼리 템플릿
_SUBQUERY_TEMPLATES = [
    "{base_query} HBM 고대역폭메모리 AI가속기 스타트업",
    "{base_query} EDA 반도체설계자동화 AI 스타트업 투자",
    "{base_query} Fab AI 반도체제조공정 PIM CXL 신생기업",
]

_DISCOVERY_PROMPT = """당신은 반도체 AI 투자 전문 분석가입니다.
아래 웹 검색 결과와 내부 보고서 컨텍스트를 기반으로 반도체 AI 관련 스타트업을 식별하고 프로파일링하세요.

[내부 보고서 컨텍스트]
{vector_context}

[웹 검색 결과]
{web_context}

[사용자 질의]
{question}

지침:
- 반도체 AI 도메인(AI칩, HBM, EDA, Fab AI, PIM, CXL 등)에 속하는 스타트업만 포함
- relevance_score는 0-1 사이, 0.6 이상인 기업만 포함
- 최소 3개, 최대 7개 스타트업 식별
- 소스 URL을 source_urls에 포함

포함 기준 (모두 충족해야 함):
- 설립 2010년 이후 기업
- 투자 단계: Pre-Seed / Seed / Series A / B / C (상장사 제외)
- 반도체 AI 스타트업: 독자 기술/제품을 개발 중인 신생 기업

명시적 제외 대상 (대기업/상장사):
- NVIDIA, Intel, Qualcomm, AMD, Broadcom, Marvell
- Samsung, SK Hynix, SK Telecom, LG, Hyundai
- TSMC, ASML, Applied Materials, Lam Research
- Google, Microsoft, Amazon, Meta, Apple
- 직원 수 1,000명 이상 또는 상장된 기업 모두 제외
"""

_KNOWN_LARGE_CORPS = {
    "nvidia", "intel", "qualcomm", "amd", "broadcom", "marvell",
    "samsung", "sk hynix", "sk telecom", "lg", "hyundai",
    "tsmc", "asml", "applied materials", "lam research",
    "google", "microsoft", "amazon", "meta", "apple",
}

_STARTUP_STAGES = {"pre-seed", "seed", "series a", "series b", "series c", "pre-series a"}


class DiscoveryAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(StartupList, method="function_calling")
        self.retriever = SemiconductorRetriever()
        self.web_search = TavilyWebSearch()
        self.tool_router = ToolRouter()

    def __call__(self, state: GraphState) -> dict:
        print("◆ [발굴 에이전트]")
        question = state.get("question", "")
        hitl_enabled = state.get("hitl_enabled", True)
        agent_queries = state.get("agent_queries", {})

        # 에이전트별 재작성 쿼리 사용
        base_query = agent_queries.get("discovery", question)

        candidates = []
        max_retries = 3
        attempt = 0

        while len(candidates) < 3 and attempt < max_retries:
            attempt += 1
            print(f"  탐색 시도 {attempt}/{max_retries}")

            # Step 1: Web Search (Query Expansion — 3개 서브쿼리, 서브쿼리당 2건)
            web_context_parts = []
            web_urls = []
            for template in _SUBQUERY_TEMPLATES:
                sub_query = template.format(base_query=base_query)
                ctx, urls = self.web_search.get_context(sub_query, max_results=2)
                if ctx:
                    web_context_parts.append(ctx)
                    web_urls.extend(u for u in urls if u not in web_urls)
            web_context = trim_list_context(web_context_parts, max_total_chars=3000)

            # Step 2: FAISS 트렌드 유사도 검증 + 컨텍스트 (k=5로 축소)
            vector_context, _ = self.retriever.get_context_with_sources(
                f"반도체 AI 스타트업 트렌드 {base_query}", k=5
            )
            vector_context = trim_context(vector_context, max_chars=1500)

            # Step 3: LLM으로 후보 발굴
            prompt = _DISCOVERY_PROMPT.format(
                vector_context=vector_context or "(내부 데이터 없음)",
                web_context=web_context or "(웹 검색 결과 없음)",
                question=question,
            )

            try:
                result = self.structured_llm.invoke(prompt)
                raw_candidates = result.candidates if result else []
            except Exception as e:
                print(f"  구조화 출력 오류: {e}")
                raw_candidates = []

            # Step 4: FAISS 트렌드 유사도 필터링
            filtered = []
            for candidate in raw_candidates:
                _, cache_hit = self.retriever.retrieve_with_cache_check(
                    f"{candidate.name} {candidate.domain} semiconductor", k=3
                )
                # relevance_score >= 0.72 청크 1개 이상 → 도메인 적합
                if cache_hit or candidate.relevance_score >= 0.6:
                    # source_urls 보강
                    if not candidate.source_urls:
                        candidate.source_urls = web_urls[:3]
                    filtered.append(candidate)
                else:
                    print(f"  관련도 낮아 제외: {candidate.name}")

            # Step 5: 대기업/상장사 후처리 필터
            before_count = len(filtered)
            filtered = [
                c for c in filtered
                if c.name.lower() not in _KNOWN_LARGE_CORPS
                and any(stage in c.investment_stage.lower() for stage in _STARTUP_STAGES)
            ]
            removed = before_count - len(filtered)
            if removed > 0:
                print(f"  대기업/상장사 {removed}개 제외")

            candidates = filtered

            if len(candidates) < 3 and attempt < max_retries:
                print(f"  후보 {len(candidates)}개 — 쿼리 확장 재시도")
                # 쿼리 재작성으로 재시도
                base_query = f"{base_query} 반도체 AI 유망 투자처 2024 2025"

        # CP-2 HITL: 발굴된 후보 확인 — 후보 선택 UX
        if hitl_enabled and candidates:
            lines = []
            for i, c in enumerate(candidates, 1):
                lines.append(
                    f"  {i}. {c.name}\n"
                    f"     도메인: {c.domain} | 단계: {c.investment_stage}\n"
                    f"     {c.description[:80]}..."
                )
            summary = "\n".join(lines)

            message = (
                f"총 {len(candidates)}개 반도체 AI 스타트업 후보가 발굴되었습니다:\n\n"
                f"{summary}\n\n"
                "첫 번째로 심층 분석할 후보를 선택하세요.\n"
                "(나머지는 이 후보 평가 후 순차적으로 진행됩니다)"
            )

            options = [c.name for c in candidates] + ["다시 탐색"]

            user_response = interrupt({
                "checkpoint_id": "CP-2",
                "message": message,
                "data": {
                    "candidates": [c.model_dump() for c in candidates],
                    "count": len(candidates),
                },
                "options": options,
                "is_blocking": True,
            })

            response_str = str(user_response).strip()

            # 재탐색 요청
            if "다시 탐색" in response_str:
                return {
                    "startup_candidates": [],
                    "candidate_pool": [],
                    "pool_offset": 0,
                    "logs": ["[Discovery] CP-2: 재탐색 요청."],
                }

            # 선택한 후보 찾기 (이름 매칭)
            selected_idx = None
            for i, c in enumerate(candidates):
                if c.name.lower() in response_str.lower() or response_str.lower() in c.name.lower():
                    selected_idx = i
                    break

            if selected_idx is not None:
                selected = candidates[selected_idx]
                rest = [c for i, c in enumerate(candidates) if i != selected_idx]
                candidates = [selected] + rest
                print(f"[Discovery] CP-2: 선택 → {selected.name}")
            else:
                print(f"[Discovery] CP-2: 기본 선택 → {candidates[0].name}")

        if not candidates:
            print("  유효한 후보를 찾지 못했습니다.")

        first_candidate = candidates[0] if candidates else None
        return {
            "candidate_pool": candidates,
            "startup_candidates": [first_candidate] if first_candidate else [],
            "pool_offset": 1,
            "logs": [f"[Discovery] Found {len(candidates)} candidates after {attempt} attempt(s). Starting with: {first_candidate.name if first_candidate else 'none'}"],
        }
