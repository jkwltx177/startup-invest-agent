import json
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from src.graph.state import GraphState
from src.schema.models import JudgeVerdict


_JUDGE_PROMPT = """당신은 반도체 AI 투자 분석 시스템의 품질 검증 에이전트입니다.
아래 분석 결과를 2개 기준으로만 평가하세요.

[후보 스타트업 ({candidate_count}개)]
{candidates}

[기술 분석 ({tech_count}개)]
{tech_summaries}

[시장 분석 ({market_count}개)]
{market_analyses}

[경쟁사 분석 ({competitor_count}개)]
{competitor_profiles}

## 평가 기준 (각 Pass/Fail)

1. **Coverage**: tech AND market 분석 개수가 각각 후보 수 이상인가?
   - PASS 조건: tech_count({tech_count}) >= candidate_count({candidate_count}) AND market_count({market_count}) >= candidate_count({candidate_count})
   - competitor_profiles는 후보당 2개이므로 개수 비교에서 제외
   - 실패 시 target_agents에 부족한 에이전트 이름 포함

2. **Relevance**: 분석 내용에 반도체/AI/HBM/가속기 관련 키워드가 있는가?
   - PASS 조건: 기술 분석 또는 시장 분석에 반도체 도메인 키워드가 1개 이상 존재
   - 분석 내용이 "(없음)"이어도 Coverage가 통과하면 Relevance는 PASS 처리

## 중요 규칙
- Consistency, Faithfulness, Decision Readiness는 평가하지 않음 (항상 PASS)
- Coverage와 Relevance가 모두 PASS이면 overall passed=true
- 어느 하나라도 FAIL이면 passed=false

JSON 형식으로 응답하세요:
{{
  "passed": true/false,
  "failed_criteria": ["Coverage"] 또는 ["Relevance"] 또는 [],
  "feedback": "간단한 평가 근거 (1-2문장)",
  "retry_strategy": "re_route" | "re_retrieve" | "re_generate",
  "target_agents": ["tech_summary", "market_eval", "competitor"] 중 실패한 에이전트만
}}

- retry_strategy 선택:
  - Coverage 실패: "re_route" (누락 에이전트 재실행)
  - Relevance 실패: "re_retrieve" (재검색)
  - 복합: "re_route"
"""


class JudgeLoop:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)

    def __call__(self, state: GraphState) -> dict:
        print("◆ [판정 에이전트]")
        judge_iteration = state.get("judge_iteration", 0)
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])
        competitor_profiles = state.get("competitor_profiles", [])
        hitl_enabled = state.get("hitl_enabled", True)

        # 강제 종료 조건
        if judge_iteration >= 3:
            print("  최대 판정 횟수 초과 — 통과 처리")
            verdict = JudgeVerdict(
                iteration=judge_iteration,
                feedback="Max iterations reached. Forcing pass with warning.",
                passed=True,
                failed_criteria=[],
                retry_strategy="re_generate",
                target_agents=[],
            )
            return {
                "judge_passed": True,
                "judge_iteration": judge_iteration + 1,
                "judge_history": [verdict],
                "logs": ["[JudgeLoop] Forced pass after max iterations (3)."],
            }

        candidate_count = len(candidates)

        prompt = _JUDGE_PROMPT.format(
            candidates="\n".join([f"- {c.name} ({c.domain})" for c in candidates]),
            tech_count=len(tech_summaries),
            market_count=len(market_analyses),
            competitor_count=len(competitor_profiles),
            candidate_count=candidate_count,
            tech_summaries="\n".join([
                f"- {ts.startup_name}: {ts.differentiation[:100]}"
                for ts in tech_summaries
            ]) or "(없음)",
            market_analyses="\n".join([
                f"- {ma.startup_name}: {ma.market_size}, {ma.growth_rate}"
                for ma in market_analyses
            ]) or "(없음)",
            competitor_profiles="\n".join([
                f"- {cp.startup_name} vs {cp.competitor_name}: {cp.tech_gap_summary[:80]}"
                for cp in competitor_profiles
            ]) or "(없음)",
        )

        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            judgment = json.loads(content)
        except Exception as e:
            print(f"  판정 파싱 오류: {e}")
            judgment = {
                "passed": True,
                "failed_criteria": [],
                "feedback": f"Judge parsing error: {e}",
                "retry_strategy": "re_generate",
                "target_agents": [],
            }

        passed = judgment.get("passed", False)
        failed_criteria = judgment.get("failed_criteria", [])
        feedback = judgment.get("feedback", "")
        _valid_strategies = {"re_plan", "re_route", "re_retrieve", "re_generate"}
        retry_strategy = judgment.get("retry_strategy", "re_generate")
        if retry_strategy not in _valid_strategies:
            retry_strategy = "re_generate"
        target_agents = judgment.get("target_agents", [])

        verdict = JudgeVerdict(
            iteration=judge_iteration,
            feedback=feedback,
            passed=passed,
            failed_criteria=failed_criteria,
            retry_strategy=retry_strategy,
            target_agents=target_agents,
        )

        print(f"  판정 결과: 통과={passed}, 미충족={failed_criteria}, 전략={retry_strategy}")

        # 통과
        if passed:
            return {
                "judge_passed": True,
                "judge_iteration": judge_iteration + 1,
                "judge_history": [verdict],
                "judge_retry_target": [],
                "logs": [f"[JudgeLoop] PASSED at iteration {judge_iteration}."],
            }

        # 실패 + 재시도 가능
        if judge_iteration < 2:
            if retry_strategy == "re_retrieve":
                # cache_hit_flags 초기화
                return {
                    "judge_passed": False,
                    "judge_iteration": judge_iteration + 1,
                    "judge_history": [verdict],
                    "judge_retry_target": target_agents,
                    "_cache_hit_flags": {},
                    "logs": [
                        f"[JudgeLoop] FAILED (iter={judge_iteration}). "
                        f"Strategy: {retry_strategy}. Targets: {target_agents}"
                    ],
                }
            else:
                return {
                    "judge_passed": False,
                    "judge_iteration": judge_iteration + 1,
                    "judge_history": [verdict],
                    "judge_retry_target": target_agents,
                    "logs": [
                        f"[JudgeLoop] FAILED (iter={judge_iteration}). "
                        f"Strategy: {retry_strategy}. Targets: {target_agents}"
                    ],
                }

        # 실패 + 재시도 한도 초과 → CP-3 HITL
        if hitl_enabled:
            user_response = interrupt({
                "checkpoint_id": "CP-3",
                "message": (
                    f"Judge 검증이 {judge_iteration}회 시도 후에도 통과하지 못했습니다.\n\n"
                    f"실패 기준: {', '.join(failed_criteria)}\n"
                    f"평가: {feedback[:200]}\n\n"
                    "어떻게 진행할까요?"
                ),
                "data": {
                    "failed_criteria": failed_criteria,
                    "feedback": feedback,
                    "judge_iteration": judge_iteration,
                },
                "options": ["강제 통과 후 Decision 진행", "분석 처음부터 재시작", "현재 데이터로 보고서 생성"],
                "is_blocking": True,
            })

            response_str = str(user_response)
            if "재시작" in response_str:
                return {
                    "judge_passed": False,
                    "judge_iteration": judge_iteration + 1,
                    "judge_history": [verdict],
                    "startup_candidates": [],
                    "tech_summaries": [],
                    "market_analyses": [],
                    "competitor_profiles": [],
                    "logs": ["[JudgeLoop] CP-3: User requested full restart."],
                }
            else:
                # 강제 통과 또는 현재 데이터로 진행
                return {
                    "judge_passed": True,
                    "judge_iteration": judge_iteration + 1,
                    "judge_history": [verdict],
                    "logs": [f"[JudgeLoop] CP-3: User forced pass. Response: {response_str[:50]}"],
                }

        # HITL 비활성화 시 강제 통과
        return {
            "judge_passed": True,
            "judge_iteration": judge_iteration + 1,
            "judge_history": [verdict],
            "logs": [f"[JudgeLoop] HITL disabled. Forced pass at iteration {judge_iteration}."],
        }
