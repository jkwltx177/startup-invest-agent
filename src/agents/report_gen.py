import asyncio
import io
import base64
import warnings
import matplotlib
matplotlib.use("Agg")   # GUI 없는 환경 대응
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.tools.token_utils import trim_candidates_str


# ────────────────────────────────────────────────────────────
# 한글 폰트 설정 (Glyph missing 경고 억제)
# ────────────────────────────────────────────────────────────
def _setup_korean_font():
    candidates = ["Apple SD Gothic Neo", "AppleGothic", "Noto Sans KR", "NanumGothic", "Malgun Gothic"]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            plt.rcParams["axes.unicode_minus"] = False
            return
    # 한글 폰트 없으면 경고만 억제
    warnings.filterwarnings("ignore", category=UserWarning, message="Glyph.*missing from font")
    plt.rcParams["axes.unicode_minus"] = False

_setup_korean_font()


# ────────────────────────────────────────────────────────────
# 시각화 헬퍼
# ────────────────────────────────────────────────────────────

def _build_competitor_table(competitor_profiles) -> str:
    """CompetitorProfile 목록 → 마크다운 비교표"""
    if not competitor_profiles:
        return ""
    lines = [
        "| 스타트업 | 경쟁사 | 기술 격차 요약 | 시장점유율 | 펀딩(USD) | 주요 파트너 |",
        "|---------|--------|-------------|:--------:|:--------:|-----------|",
    ]
    for cp in competitor_profiles:
        share = f"{cp.market_share_pct:.0f}%" if cp.market_share_pct else "—"
        funding = f"${cp.funding_total_usd:,}" if cp.funding_total_usd else "—"
        partners = ", ".join(cp.strategic_partners[:2]) if cp.strategic_partners else "—"
        gap = cp.tech_gap_summary[:70] + "…" if len(cp.tech_gap_summary) > 70 else cp.tech_gap_summary
        lines.append(f"| {cp.startup_name} | {cp.competitor_name} | {gap} | {share} | {funding} | {partners} |")
    return "\n".join(lines)


def _build_market_share_chart(competitor_profiles) -> str:
    """경쟁사 시장점유율 수평 막대 그래프 → base64 HTML img 태그"""
    data = [(cp.competitor_name, cp.market_share_pct)
            for cp in competitor_profiles if cp.market_share_pct]
    if not data:
        return ""

    names, values = zip(*sorted(data, key=lambda x: x[1]))
    fig, ax = plt.subplots(figsize=(7, max(2.5, len(data) * 0.6 + 1)))
    colors = plt.cm.Blues([0.4 + 0.5 * v / max(values) for v in values])
    bars = ax.barh(names, values, color=colors, edgecolor="white")
    ax.set_xlabel("시장점유율 (%)", fontsize=10)
    ax.set_title("경쟁사 시장점유율 (추정)", fontsize=12, fontweight="bold", pad=10)
    ax.set_xlim(0, max(values) * 1.2)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.0f}%", va="center", fontsize=9)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return f'\n\n<img src="data:image/png;base64,{img_b64}" style="max-width:100%;margin:12px 0;">\n\n'


def _build_scorecard_chart(validation_results) -> str:
    """invest 결정의 scorecard_breakdown → 수평 막대 그래프"""
    target = next((r for r in validation_results if r.investment_category == "invest"), None)
    if not target or not target.scorecard_breakdown:
        return ""

    items = list(target.scorecard_breakdown.items())
    labels, scores = zip(*items)
    fig, ax = plt.subplots(figsize=(7, max(3, len(items) * 0.55 + 1.5)))
    colors = ["#4CAF50" if s >= 7 else "#FF9800" if s >= 4 else "#F44336" for s in scores]
    bars = ax.barh(labels, scores, color=colors, edgecolor="white")
    ax.set_xlim(0, 10)
    ax.set_xlabel("점수 (0–10)", fontsize=10)
    ax.set_title(f"스코어카드 — {target.startup_name} (총점 {target.score:.0f}점)",
                 fontsize=12, fontweight="bold", pad=10)
    ax.axvline(7, color="#888", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, val in zip(bars, scores):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=9)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    return f'\n\n<img src="data:image/png;base64,{img_b64}" style="max-width:100%;margin:12px 0;">\n\n'


# ────────────────────────────────────────────────────────────
# 섹션별 LLM 프롬프트 (report_form.md 전체 목차 커버)
# ────────────────────────────────────────────────────────────

# ── 섹션 0 ──────────────────────────────────────────────────
_EXEC_SUMMARY_PROMPT = """반도체 AI 투자 보고서의 Executive Summary를 작성하세요.

[스타트업 후보]
{candidates}

[기술 분석]
{tech_summaries}

[시장 분석]
{market_analyses}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 0. Executive Summary

- **(투자구조)** 투자 방식, 투자 단계, 투자금액, 기업가치(Pre/Post) 추정
- **(기업현황)** 회사 개요 및 핵심 AI/반도체 기술 스택(Foundation Model, Agentic AI 등) 요약
- **(투자포인트)** Bessemer Checklist 기준 핵심 강점 (성장성, 자본 효율성, 기술적 해자)
- **(회수 및 수익성)** 예상 Exit 시나리오(M&A/IPO), 예상 시기, 수익률(Multiple, IRR) 추정

(최소 400자)"""


# ── 섹션 1 ──────────────────────────────────────────────────
_COMPANY_SECTION_PROMPT = """반도체 AI 투자 보고서의 회사 현황 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[기술 분석]
{tech_summaries}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 1. 회사 현황

### 1-1. 회사 개요
- 회사명, 대표명, 설립일자, 업종(AI 세부 도메인 명시), 임직원수
- 기업인증, 산업분류코드, 주소 및 연락처

### 1-2. 회사 연혁 및 주요 기술 마일스톤
- 주요 제품 출시 및 AI 모델 업데이트 이력

### 1-3. 주요 사업 및 서비스
- 핵심 AI 솔루션 아키텍처 (B2B SaaS, Vertical AI, Physical AI 등 구분)

### 1-4. 주요 인력 및 R&D 역량
- 경영진 및 핵심 AI 인력(ML/GPU 엔지니어) 현황 및 이력
- AI 거버넌스 및 윤리 정책 수립 현황

### 1-5. 주요 주주 및 자본금 변동 내역
- 기존 주요 투자자 현황 및 누적 투자 유치 금액

### 1-6. 주식관련 사채 및 Stock Option 발행 현황
- 전환사채(CB), SAFE, 스톡옵션 현황 (알려진 경우)

### 1-7. 인프라 및 주요 관계회사 현황
- 확보된 연산 자원(GPU 클러스터 등) 및 독점 데이터 파이프라인 현황
- 주요 파트너사 및 관계회사

### 1-8. 기타 사항
- 특이사항, 수상/인증, 지적재산권(특허) 현황

(최소 500자)"""


# ── 섹션 2 ──────────────────────────────────────────────────
_INVESTMENT_STRUCTURE_PROMPT = """반도체 AI 투자 보고서의 투자구조 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 2. 투자구조

### 2-1. 투자 전 자본금 및 주주 현황
- 현재 주주구성 및 지분율, 기발행 주식수

### 2-2. 투자 내역 및 상세 조건
- 투자금액, 투자방식(보통주/우선주/CB/SAFE), 인수주식수, 단가 및 기업가치(Pre/Post)
- 상세조건: 만기, 상환/전환 조건, Tag-along/Drag-along, Refixing 조건 등

### 2-3. 조합의 주목적 투자 분야 부합 여부
- AI 반도체 섹터 내 해당 기업의 전략적 적합성 평가

### 2-4. 투자금 사용 용도 및 관리 방안
- 인재 영입, GPU 인프라 확충, 데이터 확보 비용 등 구체적 명시
- 자금 집행 타임라인 및 성과 지표(KPI)

(최소 300자)"""


# ── 섹션 3 ──────────────────────────────────────────────────
_FINANCIAL_SECTION_PROMPT = """반도체 AI 투자 보고서의 재무 현황 및 Bessemer 지표 분석 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[시장 분석]
{market_analyses}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 3. 재무 현황 및 Bessemer 지표 분석

### 3-1. 요약 재무 현황
- 최근 매출액, 영업손익, 순손익, 자산/부채 현황 (공개 정보 기반 추정 가능)

### 3-2. Bessemer 효율성 지표 분석
- 효율성 점수(Efficiency Score): ARR 성장률 / Net Burn 비율
- 현금 전환 점수(Cash Conversion Score): 누적 ARR / 총 투자유치액
- 성장 내구력(Growth Endurance) 및 NRR(순매출 유지율) 추정

### 3-3. 매출 성장 추이 및 수익성 분석
- 매출 성장 속도 및 YoY 성장률 추정
- 운전자본 추이 및 현금 소진율(Burn Rate) 분석

### 3-4. 분기별/월별 매출 현황 및 현금 흐름 추정
- 현재 Runway 추정 및 다음 투자 라운드 필요 시기

(최소 300자)"""


# ── 섹션 4 ──────────────────────────────────────────────────
_MARKET_TECH_SECTION_PROMPT = """반도체 AI 투자 보고서의 사업 및 시장 현황 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[기술 분석]
{tech_summaries}

[시장 분석]
{market_analyses}

[경쟁사 분석]
{competitor_profiles}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 4. 사업 및 시장 현황 (AI 특화 분석)

### 4-1. 기술 및 솔루션 심층 분석
- AI 모델 독창성, 데이터 소스 및 품질, R&D 로드맵
- 에이전트형 AI(Agentic AI)의 자율성 및 워크플로우 실행 능력 평가

### 4-2. 사업 현황 및 마케팅 전략
- 제품별 매출 비중, 주요 매출처 분석
- AI 도입에 따른 고객 업무 효율 개선 지표(ROI) 제시

### 4-3. 시장(TAM/SAM/SOM) 및 경쟁 현황 분석
- 시장 규모(TAM/SAM/SOM) 및 성장 전망 (CAGR)
- 데이터 인프라 및 클라우드 서비스와의 밸류체인 통합성
- 주요 경쟁사 대비 포지셔닝 (상세 비교는 아래 경쟁사 표/차트 참조)

### 4-4. 차별화 경쟁력 및 진입 장벽 (AI Moat)
- 데이터 해자: 학습 데이터의 희소성 및 데이터 플라이휠 효과 분석
- 전환 비용: 고객 시스템과의 깊은 통합 및 고착화(Lock-in) 전략

(최소 400자)"""


# ── 섹션 5 ──────────────────────────────────────────────────
_REVENUE_FORECAST_PROMPT = """반도체 AI 투자 보고서의 매출 및 손익 추정 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[시장 분석]
{market_analyses}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 5. 매출 및 손익 추정

### 5-1. 회사 제시 추정 손익계산서 및 근거
- 향후 3~5년 매출 성장 시나리오 (회사 측 제시 기준)
- 주요 매출 동인(Revenue Driver) 및 가정

### 5-2. 투자사 보수적 추정 손익계산서 및 민감도 분석
- 시장 변동(수요 둔화, 경쟁 심화) 시나리오 반영
- 모델 컴퓨팅 비용(GPU 인프라) 상승 리스크 반영
- Base / Bull / Bear 케이스별 손익 추정 표
- 손익분기점(BEP) 도달 예상 시기

(최소 300자)"""


# ── 섹션 6 ──────────────────────────────────────────────────
_VALUATION_SECTION_PROMPT = """반도체 AI 투자 보고서의 밸류에이션 및 투자 수익성 분석 섹션을 작성하세요.

[스타트업 후보]
{candidates}

[시장 분석]
{market_analyses}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 6. 밸류에이션 및 투자 수익성 분석

### 6-1. 일반 가정
- Full Dilution 기준 주식수, 예상 공모가 및 Exit 시점

### 6-2. 미래 기업 가치 추정 (Multiple Value)
- 유사 AI 반도체 상장사(Nvidia, AMD, QUALCOMM 등) 및 최근 유니콘 라운드 비교
- Revenue Multiple 또는 EV/ARR Multiple 적용
- 회수 시기별 수익률 분석 (3x / 5x / 10x 시나리오, IRR)

### 6-3. 현재 기업 가치 평가 (Scorecard Method 적용)
- Bill Payne 방식 가중치 적용: 팀 역량(30%), 시장 규모(25%), 기술 혁신성(15~25%), 기타
- 지역/섹터 평균 대비 조정 계수 산출 및 단가 적정성 검토
- Pre-money Valuation 산출 결과

(최소 300자)"""


# ── 섹션 7 ──────────────────────────────────────────────────
_INVESTMENT_OPINION_PROMPT = """반도체 AI 투자 보고서의 종합 투자 검토 의견 섹션을 작성하세요.

[기술 분석]
{tech_summaries}

[시장 분석]
{market_analyses}

[투자 결정 결과]
{validation_results}

마크다운 형식으로 다음 섹션을 빠짐없이 작성하세요:

## 7. 종합 투자 검토 의견

### 7-1. 긍정적 측면 (Bessemer Checklist 기준)
- 기술적 우위, 지표 우수성, 시장 선점 가능성
- 성장성, 자본 효율성, 팀 역량 강점

### 7-2. 리스크 요인 및 대응 방안
- 기술적 한계(환각 현황 등), 데이터 저작권 리스크, 경쟁 심화 위험
- 규제 대응 역량 및 밸류에이션 리스크
- 각 리스크별 구체적 완화(Mitigation) 방안

### 7-3. 종합 의견 및 최종 권고
- 투자 승인 여부 및 근거 (스코어카드 기반)
- 사후 관리 전략 및 후속 투자 조건
- 투자 집행 전 선행 조건(Condition Precedent)

(최소 400자)"""


# ── Reflection ───────────────────────────────────────────────
_REFLECTION_PROMPT = """다음 투자 보고서를 검토하고 품질을 평가하세요.

[보고서]
{report}

다음 기준으로 검토하세요:
1. 섹션 0~8 목차 완성도 (빠진 섹션 확인)
2. 섹션 간 수치/주장 충돌 여부
3. 근거 없는 주장 (할루시네이션) 여부
4. 반도체 도메인 전문성 적절성
5. 투자 결론의 근거 충분성

JSON 형식으로 응답:
{{
  "quality_score": 0-10,
  "issues": ["문제점 목록"],
  "sections_to_regenerate": ["exec_summary", "company", "investment_structure", "financial", "market_tech", "revenue_forecast", "valuation", "investment_opinion"] 중 해당 항목,
  "is_acceptable": true/false (quality_score >= 7이면 true)
}}"""


# ────────────────────────────────────────────────────────────
# ReportAgent
# ────────────────────────────────────────────────────────────

class ReportAgent:
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0.2)

    async def _generate_section(self, prompt: str) -> str:
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            print(f"  섹션 생성 오류: {e}")
            return f"(섹션 생성 실패: {e})"

    def __call__(self, state: GraphState) -> dict:
        print("◆ [보고서 생성 에이전트]")
        candidates = state.get("startup_candidates", [])
        tech_summaries = state.get("tech_summaries", [])
        market_analyses = state.get("market_analyses", [])
        competitor_profiles = state.get("competitor_profiles", [])
        validation_results = state.get("validation_results", [])
        investment_decision = state.get("investment_decision", "hold")

        # 선택된 스타트업 결정: invest 우선 → 없으면 최고점 hold 후보 (max iter 강제 진입 시)
        selected_startup = None
        for r in validation_results:
            if r.investment_category == "invest":
                selected_startup = r.startup_name
                break
        if not selected_startup and validation_results:
            best = max(validation_results, key=lambda r: r.score)
            selected_startup = best.startup_name
            print(f"  (invest 없음 — 최고점 후보 선택: {selected_startup}, {best.score:.0f}점)")
        if not selected_startup and candidates:
            selected_startup = candidates[0].name

        # 데이터 직렬화 (토큰 절감)
        candidates_str = trim_candidates_str(candidates, max_per=120)
        tech_str = "\n".join([
            f"- {ts.startup_name}: {ts.differentiation[:120]} | 강점: {str(ts.strengths)[:80]}"
            for ts in tech_summaries
        ]) or "(기술 분석 없음)"
        market_str = "\n".join([
            f"- {ma.startup_name}: {ma.market_size[:80]}, CAGR {ma.growth_rate}, {ma.investment_attractiveness[:60]}"
            for ma in market_analyses
        ]) or "(시장 분석 없음)"
        competitor_str = "\n".join([
            f"- {cp.startup_name} vs {cp.competitor_name}: {cp.tech_gap_summary[:120]}"
            for cp in competitor_profiles
        ]) or "(경쟁사 분석 없음)"
        decision_str = "\n".join([
            f"- {r.startup_name}: {r.score:.0f}점 [{r.investment_category}] - {r.reason[:100]}"
            for r in validation_results
        ]) or f"(전체 결정: {investment_decision})"

        # 시각화 빌드
        competitor_table = _build_competitor_table(competitor_profiles)
        market_share_chart = _build_market_share_chart(competitor_profiles)
        scorecard_chart = _build_scorecard_chart(validation_results)

        # ── 8개 섹션 병렬 생성 ──────────────────────────────
        async def generate_all():
            prompts = [
                _EXEC_SUMMARY_PROMPT.format(
                    candidates=candidates_str,
                    tech_summaries=tech_str,
                    market_analyses=market_str,
                    validation_results=decision_str,
                ),
                _COMPANY_SECTION_PROMPT.format(
                    candidates=candidates_str,
                    tech_summaries=tech_str,
                ),
                _INVESTMENT_STRUCTURE_PROMPT.format(
                    candidates=candidates_str,
                    validation_results=decision_str,
                ),
                _FINANCIAL_SECTION_PROMPT.format(
                    candidates=candidates_str,
                    market_analyses=market_str,
                    validation_results=decision_str,
                ),
                _MARKET_TECH_SECTION_PROMPT.format(
                    candidates=candidates_str,
                    tech_summaries=tech_str,
                    market_analyses=market_str,
                    competitor_profiles=competitor_str,
                ),
                _REVENUE_FORECAST_PROMPT.format(
                    candidates=candidates_str,
                    market_analyses=market_str,
                    validation_results=decision_str,
                ),
                _VALUATION_SECTION_PROMPT.format(
                    candidates=candidates_str,
                    market_analyses=market_str,
                    validation_results=decision_str,
                ),
                _INVESTMENT_OPINION_PROMPT.format(
                    tech_summaries=tech_str,
                    market_analyses=market_str,
                    validation_results=decision_str,
                ),
            ]
            return await asyncio.gather(*[self._generate_section(p) for p in prompts])

        try:
            sections = asyncio.run(generate_all())
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                sections = loop.run_until_complete(generate_all())
            finally:
                loop.close()

        (exec_section, company_section, investment_structure_section,
         financial_section, market_tech_section, revenue_forecast_section,
         valuation_section, investment_opinion_section) = sections

        # ── 경쟁사 블록 (표 + 차트) ─────────────────────────
        competitor_block = ""
        if competitor_table or market_share_chart:
            competitor_block = "### 경쟁사 비교 분석\n\n"
            if competitor_table:
                competitor_block += competitor_table + "\n\n"
            if market_share_chart:
                competitor_block += "**시장점유율 차트**" + market_share_chart

        # ── 스코어카드 블록 ──────────────────────────────────
        scorecard_block = ""
        if scorecard_chart:
            scorecard_block = "### 스코어카드 시각화\n" + scorecard_chart

        # ── 레퍼런스 수집 ────────────────────────────────────
        all_urls = []
        for c in candidates:
            all_urls.extend(c.source_urls or [])
        for ts in tech_summaries:
            all_urls.extend(getattr(ts, "sources", None) or [])
        for ma in market_analyses:
            all_urls.extend(getattr(ma, "sources", None) or [])
        for cp in competitor_profiles:
            all_urls.extend(getattr(cp, "source_urls", None) or [])
        unique_urls = list(dict.fromkeys(all_urls))

        references_section = "## 8. (별첨) Reference 및 기술 실사 자료\n\n"
        if unique_urls:
            for i, url in enumerate(unique_urls, 1):
                references_section += f"{i}. {url}\n\n"
        else:
            references_section += "(참고 URL 없음)\n"

        # ── 보고서 조합 (report_form.md 전체 목차) ───────────
        report = f"""# 반도체 AI 스타트업 투자 심사 보고서

> **분석 대상:** {selected_startup or '미선정'}
> **최종 결정:** {(investment_decision or 'unknown').upper()}
> **분석 스타트업 수:** {len(candidates)}개

---

{exec_section}

{company_section}

{investment_structure_section}

{financial_section}

{market_tech_section}

{competitor_block}

{revenue_forecast_section}

{valuation_section}

{scorecard_block}

{investment_opinion_section}

---

{references_section}

---
*본 보고서는 AI 기반 자동화 분석 시스템에 의해 생성되었습니다.*
"""

        # ── Reflection: 품질 검증 ────────────────────────────
        reflection_prompt = _REFLECTION_PROMPT.format(report=report[:4000])
        try:
            import json
            refl_response = self.llm.invoke(reflection_prompt)
            refl_content = refl_response.content.strip()
            if refl_content.startswith("```"):
                refl_content = refl_content.split("```")[1]
                if refl_content.startswith("json"):
                    refl_content = refl_content[4:]
            reflection = json.loads(refl_content)
            if not reflection.get("is_acceptable", True):
                print(f"  리플렉션: 품질={reflection.get('quality_score')}, 이슈={reflection.get('issues', [])}")
        except Exception as e:
            print(f"  리플렉션 파싱 오류: {e}")

        # ── PDF 생성 ──────────────────────────────────────────
        pdf_path = None
        try:
            from src.tools.pdf_exporter import generate_pdf
            safe_name = (selected_startup or "report").replace(" ", "_").replace("/", "_")
            pdf_path = generate_pdf(
                report,
                output_dir="./output",
                filename=f"invest_{safe_name}",
            )
            print(f"  PDF 저장 완료: {pdf_path}")
        except Exception as e:
            print(f"  PDF 생성 실패: {e}")

        print("  보고서 생성 완료.")

        return {
            "final_report": report,
            "selected_startup": selected_startup,
            "report_pdf_path": pdf_path,
            "is_done": True,
            "logs": [
                f"[ReportGen] Report generated. "
                f"Selected: {selected_startup}, Decision: {investment_decision}, "
                f"PDF: {pdf_path or 'N/A'}"
            ],
        }
