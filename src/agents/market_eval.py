from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from src.graph.state import GraphState
from src.schema.models import MarketAnalysis
from src.tools.retriever import SemiconductorRetriever
from src.tools.web_search import TavilyWebSearch
from src.tools.token_utils import trim_list_context, trim_candidates_str


class MarketAnalysisList(BaseModel):
    analyses: List[MarketAnalysis] = Field(description="List of market analyses for each candidate")


_MARKET_PROMPT = """당신은 반도체 AI 시장 분석 전문가입니다.
아래 컨텍스트를 기반으로 각 스타트업의 시장 잠재력을 분석하세요.

[컨텍스트]
{context}

[분석 대상 스타트업]
{candidates}

각 스타트업에 대해 다음을 분석하세요:
- market_size: TAM/SAM/SOM 추정치 (구체적 수치 포함)
- growth_rate: CAGR 추정치
- market_position: 시장 위치 (예: Niche, Challenger, Follower)
- investment_attractiveness: 투자 매력도 평가 (High/Medium/Low + 이유)
- sources: 분석에 사용된 소스 URL
- confidence_score: 분석 신뢰도 (0-1)
"""


class MarketEvalAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(MarketAnalysisList, method="function_calling")
        self.retriever = SemiconductorRetriever()
        self.web_search = TavilyWebSearch()

    def __call__(self, state: GraphState) -> dict:
        print("◆ [시장 분석 에이전트]")
        candidates = state.get("startup_candidates", [])
        if not candidates:
            return {"market_analyses": [], "logs": ["[MarketEval] No candidates to analyze."]}

        agent_queries = state.get("agent_queries", {})
        question = agent_queries.get("market_eval", state.get("question", ""))

        # Bug fix: was [c.name for d in candidates], corrected to [c.name for c in candidates]
        candidate_names = ", ".join([c.name for c in candidates])

        all_context_parts = []
        all_sources = []

        # Vector context (k=5로 축소)
        vector_ctx, vector_sources = self.retriever.get_context_with_sources(
            f"Market analysis TAM SAM SOM CAGR semiconductor AI: {candidate_names}", k=5
        )
        if vector_ctx:
            all_context_parts.append(f"[벡터 DB 내부 리포트]\n{vector_ctx[:1500]}")
            all_sources.extend(vector_sources)

        # Web search: 상위 3개 후보만, 결과 2건씩
        print("  최신 시장 데이터 웹 검색 중")
        for c in candidates[:3]:
            web_query = f"{c.name} {c.domain} semiconductor market size TAM CAGR 2025"
            web_ctx, web_urls = self.web_search.get_context(web_query, max_results=2)
            if web_ctx:
                all_context_parts.append(web_ctx)
                all_sources.extend(u for u in web_urls if u not in all_sources)

        # 글로벌 트렌드 (2건)
        market_trend_ctx, trend_urls = self.web_search.get_context(
            "AI semiconductor market size 2025 forecast", max_results=2
        )
        if market_trend_ctx:
            all_context_parts.append(f"[글로벌 시장 트렌드]\n{market_trend_ctx}")
            all_sources.extend(u for u in trend_urls if u not in all_sources)

        context = trim_list_context(all_context_parts, max_total_chars=4000)
        candidates_str = trim_candidates_str(candidates, max_per=100)

        prompt = _MARKET_PROMPT.format(
            context=context or "(컨텍스트 없음)",
            candidates=candidates_str,
        )

        try:
            result = self.structured_llm.invoke(prompt)
            market_analyses = result.analyses if result else []
            for ma in market_analyses:
                if not ma.sources:
                    ma.sources = all_sources[:3]
                if ma.confidence_score == 0.0:
                    ma.confidence_score = 0.65
        except Exception as e:
            print(f"  구조화 출력 오류: {e}")
            market_analyses = []

        return {
            "market_analyses": market_analyses,
            "logs": [f"[MarketEval] Analyzed {len(market_analyses)} market profiles."],
        }
