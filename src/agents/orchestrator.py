from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from src.graph.state import GraphState
from src.tools.tool_router import ToolRouter


_DOMAIN_CLASSIFY_PROMPT = """당신은 반도체 AI 투자 분석 시스템의 입구 에이전트입니다.
사용자 질의를 분석하여 다음 중 하나로 분류하세요:

1. "direct" — 단순 질문/잡담/시스템 관련 질의로 즉시 답변 가능한 경우
   예: "안녕하세요", "이 시스템은 무엇인가요?", "도움말"

2. "pipeline" — 반도체 AI 스타트업 투자 분석이 필요한 경우
   예: "HBM 관련 스타트업 투자 분석", "AI 반도체 유망 기업 발굴"

사용자 질의: {question}

JSON 형식으로 응답하세요:
{{
  "route_type": "direct" or "pipeline",
  "detected_domain": "반도체 AI" or 감지된 도메인,
  "direct_answer": "직접 답변 내용 (route_type이 direct일 때만)",
  "confidence": 0.0-1.0
}}"""


class Orchestrator:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.tool_router = ToolRouter(model_name=model_name)

    def __call__(self, state: GraphState) -> dict:
        print("◆ [오케스트레이터]")
        question = state.get("question", "")
        hitl_enabled = state.get("hitl_enabled", True)

        # Step 1: 질의 분류
        prompt = _DOMAIN_CLASSIFY_PROMPT.format(question=question)
        try:
            import json
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            # JSON 파싱
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            classification = json.loads(content)
        except Exception as e:
            print(f"  분류 오류 — 파이프라인으로 대체: {e}")
            classification = {
                "route_type": "pipeline",
                "detected_domain": "반도체 AI",
                "confidence": 0.5,
            }

        route_type = classification.get("route_type", "pipeline")
        detected_domain = classification.get("detected_domain", "반도체 AI")
        confidence = classification.get("confidence", 1.0)

        # Step 2: 직접 응답
        if route_type == "direct":
            direct_answer = classification.get("direct_answer", "")
            if not direct_answer:
                direct_answer = self.llm.invoke(question).content
            return {
                "route_type": "direct",
                "direct_answer": direct_answer,
                "detected_domain": detected_domain,
                "is_done": True,
                "logs": [f"[Orchestrator] Direct response to query: {question[:50]}"],
            }

        # Step 3: 도메인 분류 불확실 → CP-1 HITL
        if confidence < 0.5 and hitl_enabled:
            user_response = interrupt({
                "checkpoint_id": "CP-1",
                "message": (
                    f"질의의 도메인을 확인하지 못했습니다 (confidence={confidence:.2f}).\n"
                    f"질의: '{question}'\n"
                    "반도체 AI 투자 분석을 계속 진행할까요?"
                ),
                "data": {"question": question, "detected_domain": detected_domain},
                "options": ["예, 계속 진행", "아니오, 중단"],
                "is_blocking": True,
            })
            if "아니오" in str(user_response):
                return {
                    "route_type": "direct",
                    "direct_answer": "사용자 요청으로 파이프라인을 중단합니다.",
                    "is_done": True,
                    "logs": ["[Orchestrator] CP-1: User stopped the pipeline."],
                }

        # Step 4: 파이프라인 — 1단계 쿼리 재작성
        rewritten_query = self.tool_router.rewrite_query(
            "supervisor", question, candidates=None
        )

        return {
            "route_type": "pipeline",
            "detected_domain": detected_domain,
            "agent_queries": {"supervisor": rewritten_query},
            "logs": [
                f"[Orchestrator] Pipeline route. Domain: {detected_domain}. "
                f"Rewritten query: {rewritten_query}"
            ],
        }
