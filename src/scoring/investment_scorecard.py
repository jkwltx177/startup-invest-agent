"""
최종 투자 판단 Scorecard (Supervisor/Decision 공통 기준)

- ① 반도체 AI 솔루션 / ② AI 반도체(팹리스) 유형 분리
- Scorecard 60% + Semiconductor 특화 25% + 산업 트렌드 15%
- Gate(최소 기준) 통과 후 가중합 → 임계값 이상이면 투자, 미만이면 보류
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class StartupType(str, Enum):
    SEMICONDUCTOR_AI_SOLUTION = "semiconductor_ai_solution"  # ① 공정/설계/분석 자동화 AI
    AI_SEMICONDUCTOR_FABLESS = "ai_semiconductor_fabless"  # ② AI 반도체 칩


class SubScores(BaseModel):
    """1~5 척도 (정수). YES/NO는 5/0으로 매핑 가능."""

    owner: int = Field(ge=1, le=5, description="창업자(Owner)")
    market: int = Field(ge=1, le=5, description="시장성")
    product_tech: int = Field(ge=1, le=5, description="제품/기술력")
    competitive_edge: int = Field(ge=0, le=5, description="경쟁 우위 YES=5 NO=0")
    track_record: int = Field(ge=0, le=5, description="실적 YES=5 NO=0")
    investment_terms: int = Field(ge=0, le=5, description="투자조건 YES=5 NO=0")

    semi_tech_diff: int = Field(ge=1, le=5, description="반도체 기술 차별성")
    product_stage: int = Field(ge=1, le=5, description="제품 단계")
    data_access: int = Field(ge=0, le=5, description="데이터 접근성")
    ecosystem_fit: int = Field(ge=0, le=5, description="생태계 적합성")
    ip_patent: int = Field(ge=0, le=5, description="IP/특허")

    trend_memory: int = Field(ge=0, le=5, description="산업 트렌드 DRAM/NAND/HBM 등")
    tech_domain: int = Field(ge=0, le=5, description="기술 적용 영역 설계vs공정")
    customer_fit: int = Field(ge=0, le=5, description="고객 산업 적합성")
    growth: int = Field(ge=0, le=5, description="성장성")


# 가중치 (합 100%)
W_SCORECARD = {
    "owner": 0.15,
    "market": 0.15,
    "product_tech": 0.10,
    "competitive_edge": 0.08,
    "track_record": 0.06,
    "investment_terms": 0.06,
}
W_SEMI = {
    "semi_tech_diff": 0.08,
    "product_stage": 0.05,
    "data_access": 0.04,
    "ecosystem_fit": 0.04,
    "ip_patent": 0.04,
}
W_TREND = {
    "trend_memory": 0.05,
    "tech_domain": 0.04,
    "customer_fit": 0.03,
    "growth": 0.03,
}

# Gate: 최소 척도 (1~5 스케일은 /5 로 정규화 전에 통과 여부)
GATES = [
    ("owner", 3),
    ("market", 3),
    ("product_tech", 3),
    ("semi_tech_diff", 3),
    ("product_stage", 2),
]

INVESTMENT_THRESHOLD = 70.0  # 총점 100 만점


@dataclass
class ScorecardResult:
    startup_type: StartupType
    sub: SubScores
    gate_passed: bool
    gate_failures: list[str]
    total_score: float  # 0~100
    recommendation: str  # "투자" | "보류"
    rationale: str


def _scale_1_5_to_pct(v: int) -> float:
    return (v / 5.0) * 100.0


def _weighted_total(sub: SubScores) -> float:
    """가중합 점수 (0~100 근사)."""
    sc = 0.0
    for k, w in W_SCORECARD.items():
        val = getattr(sub, k)
        sc += w * _scale_1_5_to_pct(min(5, max(0, val)))
    for k, w in W_SEMI.items():
        val = getattr(sub, k)
        sc += w * _scale_1_5_to_pct(min(5, max(0, val)))
    for k, w in W_TREND.items():
        val = getattr(sub, k)
        sc += w * _scale_1_5_to_pct(min(5, max(0, val)))
    return round(sc, 2)


def _check_gates(sub: SubScores) -> tuple[bool, list[str]]:
    fails = []
    for attr, min_v in GATES:
        v = getattr(sub, attr)
        if v < min_v:
            fails.append(f"{attr}<{min_v}")
    return (len(fails) == 0), fails


def evaluate_investment_scorecard(
    sub: SubScores,
    startup_type: StartupType,
) -> ScorecardResult:
    gate_ok, fails = _check_gates(sub)
    total = _weighted_total(sub)
    if not gate_ok:
        rec = "보류"
        rationale = f"Gate 미충족: {', '.join(fails)}"
    elif total >= INVESTMENT_THRESHOLD:
        rec = "투자"
        rationale = f"Gate 통과, 가중합 {total} >= {INVESTMENT_THRESHOLD}"
    else:
        rec = "보류"
        rationale = f"Gate 통과했으나 총점 {total} < {INVESTMENT_THRESHOLD}"
    return ScorecardResult(
        startup_type=startup_type,
        sub=sub,
        gate_passed=gate_ok,
        gate_failures=fails,
        total_score=total,
        recommendation=rec,
        rationale=rationale,
    )


SCORECARD_PROMPT_BLOCK = """
# 최종 투자 판단 구조 (반드시 준수)

투자 판단은 다음 세 가지 기준을 기반으로 수행된다.
- 평가 기준 구조 설계 → 분리 이유: 반도체 산업 세분화로 스타트업 유형이 2가지 이상 존재
  ① 반도체 AI 솔루션 스타트업 → 공정/설계/분석 자동화 AI 솔루션
  ② AI 반도체 스타트업(팹리스) → AI 반도체 공정/설계 기술력

① Scorecard 기본 > 60점(가중합 비중)
② Semiconductor 특화 > 25점
③ 산업 트렌드 적합성 > 15점

Scorecard Method (Subtotal=60%): 창업자 15%, 시장성 15%, 제품/기술력 10%, 경쟁우위 8%, 실적 6%, 투자조건 6%.
Threshold(척도): 창업자·시장성·제품/기술력 ≥3. 경쟁우위·실적·투자조건은 YES/NO.

Semiconductor 특화 (25%): 반도체 기술 차별성 8%, 제품 단계 5%, 데이터 접근성 4%, 생태계 적합성 4%, IP/특허 4%.
Threshold: 반도체 기술 차별성 ≥3, 제품 단계 ≥2.

산업 트렌드 (15%): 산업 트렌드 적합성 5%, 기술 적용 영역 4%, 고객 산업 적합성 3%, 성장성 3%.

각 평가 항목을 척도 기반으로 점수화한 뒤, 창업자·시장성·기술력·반도체 기술 차별성·제품 단계에 대한 Gate를 먼저 확인한다.
Gate 통과 시 가중합 총점(100점 만점)을 계산하고, 임계값(70점) 이상이면 투자, 미만이면 보류.
"""
