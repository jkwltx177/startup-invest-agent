from typing import List
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from src.graph.state import GraphState
from src.schema.models import ValidationResult
from src.tools.token_utils import trim_candidates_str


class ValidationResultList(BaseModel):
    results: List[ValidationResult] = Field(description="Scoring results for each candidate")


_DECISION_PROMPT = """당신은 반도체 AI 투자 전문 파트너입니다.
아래 분석 데이터를 기반으로 **평가 대상 스타트업(현재 후보)**에 대한 투자 결정을 내리세요.

[후보 스타트업]
{candidates}

[기술 분석]
{tech_summaries}

[시장 분석]
{market_analyses}

[경쟁사 분석]
{competitor_profiles}

---

## 스코어카드 (1~5점, 가중치 적용 → weighted_avg 1~5)

### ① Scorecard Method (60%)
| 항목 | 가중치 | Gate(★) | Score Mapping |
|------|--------|---------|---------------|
| 창업자 | 15% | | 5=Ex-NVIDIA/Google/TSMC 창업자, 4=반도체/AI 10년+, 3=관련산업경험, 2=스타트업경험만, 1=관련경험없음 |
| 시장성 | 15% | ★ | 5=TAM>$50B, 4=TAM>$20B, 3=TAM>$5B, 2=niche market, 1=시장불명확 → 1이면 즉시 hold |
| 제품/기술 | 10% | ★ | 5=양산chip, 4=tape-out완료, 3=PoC/prototype, 2=architecture설계, 1=아이디어 → 1이면 즉시 hold |
| 경쟁우위 | 8% | ★ | 5=GPU대비성능/전력우위, 4=명확한차별점, 3=일부차별점, 2=약한차별점, 1=차별성없음 → 1이면 즉시 hold |
| 실적 | 6% | | 5=design win/고객존재, 4=LOI체결, 3=파일럿, 2=검증중, 1=고객없음 |
| 투자조건 | 6% | ★ | 5=seed/seriesA적정밸류, 4=약간높음, 3=높음, 2=매우높음, 1=과대밸류/late stage → 1이면 즉시 hold |

### ② Semiconductor 특화 (25%)
| 항목 | 가중치 | Gate(★) | Score Mapping |
|------|--------|---------|---------------|
| 기술차별성 | 8% | | 5=독자NPU/AI加속기, 4=custom AI chip, 3=기존chip개선, 2=FPGA기반, 1=SW only |
| 제품단계 | 5% | ★ | 5=양산chip, 4=tape-out, 3=silicon validation, 2=RTL완료, 1=concept → 1이면 즉시 hold |
| 데이터접근성 | 4% | | 5=fab/고객데이터확보, 4=파트너데이터, 3=공개데이터활용, 2=제한적, 1=없음 |
| 생태계 | 4% | | 5=SDK/SW stack제공, 4=API/tools, 3=일부SW, 2=로드맵만, 1=hw only |
| IP/특허 | 4% | | 5=핵심특허존재, 4=출원중, 3=일부특허, 2=영업비밀, 1=없음 |

### ③ 산업 트렌드 (15%)
| 항목 | 가중치 | Gate(★) | Score Mapping |
|------|--------|---------|---------------|
| 트렌드적합성 | 5% | | 5=AI/HBM/DRAM트렌드직접관련, 4=간접관련, 3=보통, 2=약한연관, 1=무관 |
| 기술영역 | 4% | | 5=설계+공정+시스템, 4=2개영역, 3=1개영역深, 2=일부, 1=단일영역 |
| 고객산업 | 3% | ★ | 5=hyperscaler/foundry, 4=IDM/fabless, 3=B2B일반, 2=불명확, 1=고객불명확 → 1이면 즉시 hold |
| 성장성 | 3% | | 5=roadmap/확장가능, 4=명확한계획, 3=일부계획, 2=단기계획만, 1=단일제품 |

---

## 결정 규칙
1. Gate 항목(★) 중 하나라도 1점 → 즉시 investment_category = "hold"
2. weighted_avg = Σ(score_i × weight_i) / Σ(weight_i)  (모든 가중치 합 = 1.0)
3. weighted_avg >= 4.0 → "invest"
4. weighted_avg < 4.0  → "hold"

각 스타트업에 대해 다음을 제공하세요:
- startup_name: 스타트업 이름
- score: weighted_avg × 20 (5점→100점 환산, 4.0→80점)
- passed: score >= 80 이면 True
- reason: 투자 결정 이유 (구체적, 200자 이상, 각 항목 점수 근거 포함)
- investment_category: "invest" 또는 "hold"
- scorecard_breakdown: 항목별 점수 딕셔너리 (예: {{"창업자": 4, "시장성": 5, ...}})
- investment_risk: 핵심 투자 리스크 요약
"""


class InvestmentDecisionAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(ValidationResultList, method="function_calling")

    def __call__(self, state: GraphState) -> dict:
        print("◆ [투자 결정 에이전트]")
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])
        competitor_profiles = state.get("competitor_profiles", [])
        hitl_enabled = state.get("hitl_enabled", True)

        if not candidates:
            return {
                "validation_results": [],
                "investment_decision": "hold",
                "logs": ["[투자 결정] 평가할 후보가 없습니다."],
            }

        # 현재 후보 이름 기준으로 분석 데이터 필터링
        current_names = {c.name for c in candidates}
        filtered_tech = [ts for ts in tech_summaries if ts.startup_name in current_names]
        filtered_market = [ma for ma in market_analyses if ma.startup_name in current_names]
        filtered_competitor = [cp for cp in competitor_profiles if cp.startup_name in current_names]

        prompt = _DECISION_PROMPT.format(
            candidates=trim_candidates_str(candidates, max_per=120),
            tech_summaries="\n".join([
                f"- {ts.startup_name}: {ts.differentiation[:100]} | 강점: {str(ts.strengths)[:80]}"
                for ts in filtered_tech
            ]) or "(기술 분석 데이터 없음)",
            market_analyses="\n".join([
                f"- {ma.startup_name}: {ma.market_size[:80]}, CAGR {ma.growth_rate}, {ma.investment_attractiveness[:60]}"
                for ma in filtered_market
            ]) or "(시장 분석 데이터 없음)",
            competitor_profiles="\n".join([
                f"- {cp.startup_name} vs {cp.competitor_name}: {cp.tech_gap_summary[:100]}"
                for cp in filtered_competitor
            ]) or "(경쟁사 분석 데이터 없음)",
        )

        # CP-3.5: 분석 결과 확인 후 투자 평가 진행
        if hitl_enabled and (filtered_tech or filtered_market or filtered_competitor):
            tech_preview = "\n".join([
                f"  • {ts.startup_name}: {ts.differentiation[:100]}"
                f"\n    강점: {', '.join(ts.strengths[:2]) if ts.strengths else '-'}"
                for ts in filtered_tech
            ]) or "  (없음)"

            market_preview = "\n".join([
                f"  • {ma.startup_name}: {ma.market_size[:80]}, CAGR {ma.growth_rate}"
                f"\n    {ma.investment_attractiveness[:80]}"
                for ma in filtered_market
            ]) or "  (없음)"

            competitor_preview = "\n".join([
                f"  • {cp.startup_name} vs {cp.competitor_name}: {cp.tech_gap_summary[:80]}"
                for cp in filtered_competitor
            ]) or "  (없음)"

            msg = (
                "══════════════════════════════\n"
                "  에이전트 분석 결과 확인\n"
                "══════════════════════════════\n\n"
                f"【기술 분석】\n{tech_preview}\n\n"
                f"【시장 분석】\n{market_preview}\n\n"
                f"【경쟁사 분석】\n{competitor_preview}\n\n"
                "위 분석 데이터를 확인하셨습니까?\n"
                "투자 스코어링을 진행하려면 '투자 평가 진행'을 선택하세요."
            )
            resp = interrupt({
                "checkpoint_id": "CP-3.5",
                "message": msg,
                "data": {
                    "tech_summaries": [t.model_dump() for t in filtered_tech],
                    "market_analyses": [m.model_dump() for m in filtered_market],
                    "competitor_profiles": [c.model_dump() for c in filtered_competitor],
                },
                "options": ["투자 평가 진행", "분석 재실행"],
                "is_blocking": True,
            })
            if "재실행" in str(resp):
                return {
                    "validation_results": [],
                    "investment_decision": None,
                    "judge_passed": False,
                    "logs": ["[투자 결정] CP-3.5: 분석 재실행 요청."],
                }

        try:
            result = self.structured_llm.invoke(prompt)
            results = result.results if result else []

            # investment_category 재확인 (80점 = weighted_avg 4.0 기준)
            for r in results:
                if r.score >= 80:
                    r.investment_category = "invest"
                    r.passed = True
                else:
                    r.investment_category = "hold"
                    r.passed = False

        except Exception as e:
            print(f"  구조화 출력 오류: {e}")
            results = []

        # 전체 투자 결정 요약
        if results:
            invest_count = sum(1 for r in results if r.investment_category == "invest")
            overall_decision = "invest" if invest_count > 0 else "hold"
        else:
            overall_decision = "hold"

        # CP-4 HITL: 투자 결정 확인 (HOLD이면 스킵 — 보고서 미생성)
        if hitl_enabled and results and overall_decision != "hold":
            # 스타트업 기본 정보
            candidate_preview = "\n".join([
                f"  ▶ {c.name} | {c.domain} | {c.investment_stage}\n"
                f"    {c.description[:120]}..."
                for c in candidates
            ])

            # 기술 분석
            tech_preview = "\n".join([
                f"  • {ts.startup_name}: {ts.differentiation[:100]}\n"
                f"    강점: {', '.join(ts.strengths[:2]) if ts.strengths else '-'}"
                for ts in filtered_tech
            ]) or "  (없음)"

            # 시장 분석
            market_preview = "\n".join([
                f"  • {ma.startup_name}: {ma.market_size[:80]}, CAGR {ma.growth_rate}\n"
                f"    {ma.investment_attractiveness[:80]}"
                for ma in filtered_market
            ]) or "  (없음)"

            # 경쟁사 분석
            competitor_preview = "\n".join([
                f"  • {cp.startup_name} vs {cp.competitor_name}: {cp.tech_gap_summary[:80]}"
                for cp in filtered_competitor
            ]) or "  (없음)"

            # 스코어카드
            score_preview = "\n".join([
                f"  • {r.startup_name}: {r.score:.0f}점 [{r.investment_category.upper()}]\n"
                f"    {r.reason[:100]}..."
                + (
                    "\n" + "\n".join(f"    - {k}: {v}" for k, v in (r.scorecard_breakdown or {}).items())
                    if r.scorecard_breakdown else ""
                )
                for r in results
            ])

            message = (
                "══════════════════════════════\n"
                "  투자 분석 데이터 요약\n"
                "══════════════════════════════\n\n"
                f"【스타트업 정보】\n{candidate_preview}\n\n"
                f"【기술 분석】\n{tech_preview}\n\n"
                f"【시장 분석】\n{market_preview}\n\n"
                f"【경쟁사 분석】\n{competitor_preview}\n\n"
                f"【투자 스코어카드】\n{score_preview}\n\n"
                f"종합 의견: {overall_decision.upper()}\n\n"
                "위 데이터를 검토하셨습니다. 보고서를 생성할까요?"
            )

            user_response = interrupt({
                "checkpoint_id": "CP-4",
                "message": message,
                "data": {
                    "results": [r.model_dump() for r in results],
                    "overall_decision": overall_decision,
                },
                "options": ["예, 보고서 생성", "아니오, 분석 재검토"],
                "is_blocking": True,
            })

            if "재검토" in str(user_response):
                return {
                    "validation_results": results,
                    "investment_decision": None,
                    "judge_passed": False,
                    "logs": ["[투자 결정] CP-4: 분석 재검토 요청."],
                }

        return {
            "validation_results": results,
            "investment_decision": overall_decision,
            "logs": [
                f"[투자 결정] {len(results)}개 스타트업 평가 완료. 종합: {overall_decision}"
            ],
        }
