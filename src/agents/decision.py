"""
투자 결정 — Scorecard 60% + Semi 25% + Trend 15%, Gate 후 가중합.
한 번에 한 후보(`evaluation_target_name`)만 평가.
"""
from typing import List, Optional

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.graph.state import GraphState
from src.schema.models import StartupProfile, TechSummary, MarketAnalysis, ValidationResult
from src.scoring.investment_scorecard import (
    StartupType,
    SubScores,
    evaluate_investment_scorecard,
    SCORECARD_PROMPT_BLOCK,
)
from src.utils.human_loop import human_approve


class LLMScoreFill(BaseModel):
    """LLM이 분석 텍스트로부터 척도를 채움."""

    startup_type: str = Field(
        description="semiconductor_ai_solution 또는 ai_semiconductor_fabless"
    )
    owner: int = Field(ge=1, le=5)
    market: int = Field(ge=1, le=5)
    product_tech: int = Field(ge=1, le=5)
    competitive_edge_yes: bool
    track_record_yes: bool
    investment_terms_yes: bool
    semi_tech_diff: int = Field(ge=1, le=5)
    product_stage: int = Field(ge=1, le=5)
    data_access_yes: bool
    ecosystem_fit_yes: bool
    ip_patent_yes: bool
    trend_memory_yes: bool
    tech_domain_yes: bool
    customer_fit_yes: bool
    growth_yes: bool


def _pick(
    candidates: List[StartupProfile],
    tech: List[TechSummary],
    market: List[MarketAnalysis],
    name: str,
) -> tuple[Optional[StartupProfile], Optional[TechSummary], Optional[MarketAnalysis]]:
    n = (name or "").strip().lower()
    c = next((x for x in candidates if (x.name or "").strip().lower() == n), None)
    t = next((x for x in tech if (x.startup_name or "").strip().lower() == n), None)
    m = next((x for x in market if (x.startup_name or "").strip().lower() == n), None)
    return c, t, m


def _to_sub_scores(llm: LLMScoreFill) -> tuple[SubScores, StartupType]:
    st = StartupType.SEMICONDUCTOR_AI_SOLUTION
    if "fabless" in llm.startup_type.lower() or llm.startup_type == "ai_semiconductor_fabless":
        st = StartupType.AI_SEMICONDUCTOR_FABLESS

    return SubScores(
        owner=llm.owner,
        market=llm.market,
        product_tech=llm.product_tech,
        competitive_edge=5 if llm.competitive_edge_yes else 0,
        track_record=5 if llm.track_record_yes else 0,
        investment_terms=5 if llm.investment_terms_yes else 0,
        semi_tech_diff=llm.semi_tech_diff,
        product_stage=llm.product_stage,
        data_access=5 if llm.data_access_yes else 0,
        ecosystem_fit=5 if llm.ecosystem_fit_yes else 0,
        ip_patent=5 if llm.ip_patent_yes else 0,
        trend_memory=5 if llm.trend_memory_yes else 0,
        tech_domain=5 if llm.tech_domain_yes else 0,
        customer_fit=5 if llm.customer_fit_yes else 0,
        growth=5 if llm.growth_yes else 0,
    ), st


class InvestmentDecisionAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.struct = self.llm.with_structured_output(LLMScoreFill)

    def __call__(self, state: GraphState) -> dict:
        print("\n>>> [decision] 투자 판단 (Scorecard + Gate)", flush=True)

        target_name = state.get("evaluation_target_name") or ""
        candidates = state.get("startup_candidates") or []
        tech = state.get("tech_summaries") or []
        market = state.get("market_analyses") or []
        idx = int(state.get("candidate_eval_index", 0) or 0)

        c, t, m = _pick(candidates, tech, market, target_name)
        if not c:
            vr = ValidationResult(
                startup_name=target_name or "Unknown",
                passed=False,
                score=0.0,
                reason="후보/분석 데이터 없음",
            )
            return _pack_fail(idx, vr)

        prompt = f"""{SCORECARD_PROMPT_BLOCK}

다음 스타트업 1곳에 대해 Scorecard 척도를 채우세요. 증거는 아래 분석 텍스트에만 기반하세요.

## 후보
{c.model_dump_json(ensure_ascii=False)}

## 기술 요약
{t.model_dump_json(ensure_ascii=False) if t else "없음"}

## 시장 분석
{m.model_dump_json(ensure_ascii=False) if m else "없음"}

startup_type: 반도체 AI 솔루션이면 semiconductor_ai_solution, AI 반도체 칩/팹리스면 ai_semiconductor_fabless
YES/NO 항목은 시그널이 있으면 true.
"""
        try:
            fill = self.struct.invoke(prompt)
            sub, stype = _to_sub_scores(fill)
            result = evaluate_investment_scorecard(sub, stype)
            passed = result.recommendation == "투자"
            vr = ValidationResult(
                startup_name=c.name,
                passed=passed,
                score=result.total_score,
                reason=f"[{result.startup_type.value}] Gate={result.gate_passed}, 총점={result.total_score}, {result.rationale}",
            )
            print(
                f"   [decision] {c.name}: {result.recommendation} (총점 {result.total_score})",
                flush=True,
            )
        except Exception as e:
            vr = ValidationResult(
                startup_name=c.name,
                passed=False,
                score=0.0,
                reason=f"Scorecard 오류: {e}",
            )
            passed = False
            print(f"   [decision] 오류: {e}", flush=True)

        if passed:
            if not human_approve("decision", f"{vr.startup_name} 투자 판정. 보고서 작성할까요?"):
                return {
                    "validation_results": [vr],
                    "last_decision_passed": False,
                    "candidate_eval_index": idx + 1,
                    "all_hold": False,
                }
            return {
                "validation_results": [vr],
                "last_decision_passed": True,
                "candidate_eval_index": idx,
                "all_hold": False,
                "selected_startup": c.name,
            }

        if not human_approve("decision", f"{vr.startup_name} 보류. 다음 순위로 진행할까요?"):
            return {
                "validation_results": [vr],
                "last_decision_passed": False,
                "candidate_eval_index": len(candidates),
                "all_hold": True,
            }

        return {
            "validation_results": [vr],
            "last_decision_passed": False,
            "candidate_eval_index": idx + 1,
            "all_hold": False,
        }


def _pack_fail(idx: int, vr: ValidationResult) -> dict:
    return {
        "validation_results": [vr],
        "last_decision_passed": False,
        "candidate_eval_index": idx + 1,
        "all_hold": False,
    }
