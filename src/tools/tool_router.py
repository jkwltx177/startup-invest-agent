from typing import List, TYPE_CHECKING
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    from src.graph.state import GraphState


class ToolRouter:
    """에이전트별 툴 결정 및 쿼리 재작성"""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def decide(self, agent_name: str, state: "GraphState") -> List[str]:
        """
        에이전트와 캐시 상태에 따라 사용할 툴 목록 반환.
        Returns: List of tool names — "vector" and/or "web"
        """
        cache_hit_flags: dict = state.get("_cache_hit_flags", {})

        if agent_name == "discovery":
            # Discovery는 항상 웹 검색 우선
            return ["web"]

        elif agent_name in ("tech_summary", "competitor"):
            # 캐시 HIT 시 벡터만, MISS 시 벡터 + 웹
            if cache_hit_flags.get(agent_name, False):
                return ["vector"]
            else:
                return ["vector", "web"]

        elif agent_name == "market_eval":
            # Market Eval은 항상 hybrid
            return ["vector", "web"]

        else:
            return ["vector"]

    def rewrite_query(self, agent_name: str, question: str, candidates: List = None) -> str:
        """
        GPT-4o-mini로 에이전트별 전문 쿼리 생성.
        """
        candidate_names = ""
        if candidates:
            try:
                candidate_names = ", ".join([c.name for c in candidates])
            except AttributeError:
                candidate_names = str(candidates)

        agent_instructions = {
            "discovery": (
                "반도체 AI 스타트업 발굴을 위한 검색 쿼리. "
                "HBM, AI가속기, EDA, Fab AI, PIM, CXL 등 반도체 Value Chain 관점에서 구체적으로 작성."
            ),
            "tech_summary": (
                f"다음 스타트업들의 핵심 기술 분석 쿼리: {candidate_names}. "
                "기술 차별성, 특허, 알고리즘, 아키텍처 중심으로 작성."
            ),
            "market_eval": (
                f"다음 스타트업들의 시장 규모 분석 쿼리: {candidate_names}. "
                "TAM/SAM/SOM, CAGR, 시장 점유율, 경쟁 구도 중심으로 작성."
            ),
            "competitor": (
                f"다음 스타트업들의 경쟁사 분석 쿼리: {candidate_names}. "
                "동일 도메인 경쟁사, 기술 격차, 자금 조달 현황 중심으로 작성."
            ),
        }

        instruction = agent_instructions.get(
            agent_name,
            f"{agent_name} 에이전트를 위한 반도체 AI 분야 검색 쿼리 작성."
        )

        prompt = f"""다음 사용자 질의를 {agent_name} 에이전트의 목적에 맞게 재작성하세요.

사용자 질의: {question}
목적: {instruction}

재작성된 검색 쿼리만 출력하세요 (한 문장, 50자 이내):"""

        try:
            response = self.llm.invoke(prompt)
            rewritten = response.content.strip()
            # 따옴표 제거
            rewritten = rewritten.strip('"').strip("'")
            return rewritten
        except Exception as e:
            print(f"[ToolRouter] rewrite_query error: {e}")
            return question
