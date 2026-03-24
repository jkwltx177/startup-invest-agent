# Semiconductor AI Startup Investment Evaluation Agent

반도체·AI 도메인 스타트업을 대상으로, RAG와 멀티 에이전트 파이프라인으로 **후보 발굴 → 순차 심사 → 투자/보류 판단 → 보고서**까지 이어지는 프로젝트입니다.

## Features

- **pdfplumber 기반 정밀 전처리**: 기술 문서의 레이아웃을 보존하며 페이지, 파일명, 수정일자 등 메타데이터 자동 추출
- **Adaptive Loop Orchestration**: Supervisor가 데이터 품질(Judge)에 따라 탐색과 분석 단계를 동적으로 조절
- **Branching & Multi-hop Retrieval**: 질의 확장 및 다단계 검색을 통한 기술적 해자(Moat) 및 시장 규모(TAM/SAM/SOM) 정밀 분석
- **Reflection 기반 보고서 생성**: 섹션별 순차 생성 및 자가 검증 루프를 통한 할루시네이션(환각) 최소화

## Evaluation Metrics

| Metric | Score | Note |
| :--- | :--- | :--- |
| **Embedding Recall@k** | **0.85** | BGE-m3-ko 기반 한국어 임베딩 벤치마크 (AutoRAG 기준) |
| **Hit Rate@10** | **0.90** | 반도체 도메인 특화 문서 검색 정확도 |
| **MRR (Mean Reciprocal Rank)** | **0.78** | 최상단 검색 결과의 정답 관련성 |

## Architecture

![System Architecture](./semiconductor_ai_investment_flowchart_v3.svg)

## 1. Overview

| 항목 | 내용 |
| --- | --- |
| **Domain** | Semiconductor AI (AI 칩, EDA, Fab AI, 설계 자동화 등) |
| **방식** | LangGraph 기반 오케스트레이션 + Agentic RAG(FAISS) |
| **목표** | 내부 문서·검색 맥락을 바탕으로 기술·시장·경쟁을 정리하고, Scorecard 규칙에 따라 투자/보류를 판단한 뒤 투자 검토 보고서를 산출 |

## 2. 파이프라인 흐름 (요약)

1. **발굴(Discovery)**  
   질의를 확장해 RAG로 후보를 모으고, 관련도 기준 **상위 5개**만 둡니다.
2. **순차 심사**  
   한 번에 한 기업만 대상으로 `기술 요약 → 시장 분석 → 경쟁사 분석 → 투자 판단` 순으로 진행합니다.  
   **보류**면 다음 순위로 넘어가고, **투자**로 확정되면 곧바로 보고서 단계로 갑니다.  
   5개 모두 보류면 보류 종합 보고서를 작성합니다.
3. **투자 판단**  
   Scorecard(기본 60% + 반도체 특화 25% + 산업 트렌드 15%)와 Gate·임계값에 따라 **투자 / 보류**를 판정합니다. (상세 기준은 `src/scoring/investment_scorecard.py` 참고)
4. **보고서**  
   아래 [투자 검토 보고서](#4-투자-검토-보고서) 절 참고.

선택적으로 `HUMAN_IN_THE_LOOP` 환경 변수로 주요 단계에서 사용자 확인을 받을 수 있습니다.

## 3. 에이전트 역할

| 에이전트 | 역할 |
| --- | --- |
| **Supervisor** | 후보 유무·순번에 따라 발굴 또는 단일 후보 평가(기술→시장→경쟁→판단)로 라우팅 |
| **Discovery** | RAG 기반 후보 프로필 추출, 상위 5개 랭킹 |
| **Tech Summary** | 현재 평가 대상 기업의 기술 요약 |
| **Market Eval** | 동일 대상의 시장·성장성 분석 |
| **Competitor** | 동일 대상의 경쟁 구도 스캔 |
| **Decision** | Scorecard·Gate 적용 후 투자/보류 |
| **Report** | 투자 검토 보고서(또는 보류 보고서) Markdown 작성 및 PDF 저장 |

## 각 에이전트 키포인트


## Supervisor
전체 파이프라인의 라우팅 컨트롤러.

`judge_quality()`로 후보·기술분석·시장분석의 커버리지 점수(0~1.0)를 산출하고, GPT-4o-mini에게 현재 상태를 전달하여 `next_agent`를 결정합니다.

```
coverage_score:
  candidates 존재      → +0.3
  tech_summaries 충분  → +0.3
  market_analyses 충분 → +0.4
  ────────────────────────────
  1.0 달성 시 'decision'으로 라우팅
```

---

## DiscoveryAgent

① 질의를 반도체 Value Chain 기준 Sub-query로 분해 (Query Expansion)
② 각 Sub-query 병렬 검색 → 결과 Fusion → 중복 제거 → Top-K 선정
③ Judge: 후보 수, 반도체 관련성, 스타트업 여부, 트렌드 점수 평가
④ 미달 시 Query Rewrite + 도메인 필터 조정 후 재탐색 (최대 3회)
⑤ CP-2 HITL: 통과 후 사람에게 후보 확정 요청

### Judge 기준

```
- 후보 수가 너무 적은가
- 타겟 도메인(반도체) 외 산업이 섞였는가
- 같은 회사가 중복되는가
- 스타트업인가
    - 빠른 확장과 시장 선점
    - 상당히 빠름 (10배 성장 등)
    - 혁신적이고 독창적인 기술·서비스 중심
    - 매우 높은 리스크 (시장, 기술, 고객 관점)
    - M&A, IPO 등 Exit 전략 존재
    - 투자 중심 (VC, 엔젤 등)
- 트렌드 점수 낮으면 재탐색
```

---

## TechSummaryAgent & CompetitorAgent

**포인트: Memory-first Retrieval + Post-Retrieval Re-ranking + Self-Evaluation Loop**

- GraphState에 저장된 요약 캐시를 우선 조회하여 기존 분석 결과 재사용
- 정보 부족 시에만 웹 검색을 추가로 수행하여 최신 데이터 보완
- Self-Evaluation Loop로 기술 설명의 구체성·출처 일관성·핵심 지표 포함 여부를 검증하고 필요 시 재검색 또는 재생성 수행

---

## InvestmentDecisionAgent

스코어카드 방식으로 평가합니다.

- **70점 이상** → `passed = True` (투자 권고)
- **전원 미달** → `all_hold = True` (전부 보류)
- HITL 승인 후 보고서 단계 진입

> 각 항목에서 **Score = 1이면 즉시 `risk_flag = 1`** 로 Decision Logic에 넘겨 보류 판단합니다.

---

### ① Scorecard Method 기반 항목 (60%)

| 항목 | 비중 | 평가 의의 | Score Mapping |
|---|---|---|---|
| 창업자 | 15% | 팀 역량 | 5: Ex-NVIDIA/Google/TSMC 창업자<br>4: 반도체/AI 10년+ 경험<br>3: 관련 산업 경험 있음<br>2: 스타트업 경험만 있음<br>1: 관련 경험 없음 |
| 시장성 | 15% | 시장 크기 | 5: TAM > $50B AI semiconductor<br>4: TAM > $20B<br>3: TAM > $5B<br>2: niche market<br>1: 시장 불명확 ⚑ |
| 제품/기술 | 10% | 기술 실행력 | 5: 양산 chip 존재<br>4: tape-out 완료<br>3: PoC / prototype<br>2: architecture 설계만<br>1: 아이디어 단계 ⚑ |
| 경쟁 우위 | 8% | 진입장벽 | 5: GPU 대비 성능/전력 우위 있음<br>1: 차별성 없음 ⚑ |
| 실적 | 6% | 시장 검증 | 5: design win / 고객 존재<br>1: 고객 없음 |
| 투자조건 | 6% | 투자 리스크 | 5: seed / series A 적정 valuation<br>1: 과대 valuation / late stage ⚑ |

---

### ② Semiconductor 특화 항목 (25%)

| 항목 | 비중 | 평가 의의 | Score Mapping |
|---|---|---|---|
| 반도체 기술 차별성 | 8% | 핵심 경쟁력 | 5: 독자 NPU/AI accelerator architecture<br>4: custom AI chip 구조<br>3: 기존 chip 개선<br>2: FPGA 기반<br>1: SW only |
| 제품 단계 | 5% | 실행력 | 5: 양산 chip<br>4: tape-out<br>3: silicon validation<br>2: RTL 완료<br>1: concept ⚑ |
| 데이터 접근성 | 4% | AI 성능 핵심 | 5: fab / 고객 데이터 확보<br>1: 데이터 없음 |
| 생태계 적합성 | 4% | 시장 진입 | 5: SDK / SW stack 제공<br>1: hardware only |
| IP / 특허 | 4% | 장기 경쟁력 | 5: 핵심 특허 존재<br>1: 특허 없음 |

---

### ③ 산업 트렌드 적합성 (15%)

| 항목 | 비중 | 평가 의의 | Score Mapping |
|---|---|---|---|
| 산업 트렌드 적합성 | 5% | 타이밍 | 5: AI / HBM / DRAM 트렌드 직접 관련<br>1: 트렌드와 무관 |
| 기술 적용 영역 | 4% | 시장 크기 | 5: 설계 + 공정 + 시스템 적용<br>1: 단일 영역 |
| 고객 산업 적합성 | 3% | 수요 | 5: hyperscaler / foundry 고객 가능<br>1: 고객 불명확 ⚑ |
| 성장성 | 3% | 확장성 | 5: roadmap 존재 / 확장 가능<br>1: 단일 제품 |

---

> ⚑ 표시 항목은 Score = 1이면 즉시 `risk_flag = 1` → 보류 판단

## 4. 투자 검토 보고서

투자·보류 여부와 관계없이, 보고서 에이전트는 **기관 투자 검토 문서** 형태에 가깝게 Markdown을 만듭니다.

- **문서 대제목**: 맨 위에 보고서 전체를 나타내는 제목 한 줄.
- **SUMMARY**: 의사결정용 핵심 요약(서술 중심, 필요 시 소형 표).
- **목차**: 본문에 실제로 포함된 절 제목만 bullet 로 정리.
- **본문**: 번호 절(`# 1.`, `# 2.` …)과 소제목, 비교·재무·리스크 등에 활용할 **Markdown 표**.  
  내부 데이터가 부족한 항목은 검토용 가정·시나리오로 보완할 수 있으며, 해당 경우 표·절 아래에 **가정·추정**임을 구분하는 문구를 둡니다.
- **REFERENCE**: 본문·SUMMARY 작성에 실제로 사용한 출처만, 기관 보고서 / 학술 논문 / 웹페이지 형식에 맞춰 문서 **맨 끝**에 정리합니다.  
  본문·SUMMARY 안에는 인라인 출처나 URL 나열을 넣지 않습니다.

생성된 Markdown은 `reports/` 아래에 저장되며, 동일 파일명 기준으로 PDF로 내보낼 수 있습니다.  
보고서 본문에는 구현 세부(외부 서비스 이름, 키, 연동 방식 등)를 쓰지 않도록 프롬프트가 잡혀 있습니다.

## 5. Tech Stack

| 구분 | 내용 |
| --- | --- |
| Framework | LangGraph, LangChain, Python 3.11+ |
| LLM | OpenAI 호환 채팅 모델(기본 `gpt-4o-mini` 등, 에이전트별 설정) |
| Retrieval | FAISS + Hugging Face 임베딩(기본 `dragonkue/BGE-m3-ko`) |
| 문서 | PDF 로딩(pdfplumber), Markdown → PDF(WeasyPrint 등) |
| 선택 | 웹 검색 보강(Tavily 연동, 보고서 보조 맥락·REFERENCE용) |

## 6. 디렉터리 구조

```text
├── src/
│   ├── main.py                 # 샘플 실행 진입점
│   ├── graph/                  # LangGraph 워크플로·State
│   ├── agents/                 # Supervisor, Discovery, Tech/Market/Competitor, Decision, Report
│   ├── scoring/                # 투자 Scorecard·Gate
│   ├── schema/                 # Pydantic 모델
│   ├── report/                 # 보고서 검증·PDF
│   ├── tools/                  # RAG Retriever, 웹 검색
│   └── utils/                  # 휴먼 인 더 루프 등
├── scripts/
│   ├── run_full.py             # 전체 파이프라인 실행(권장)
│   └── build_faiss_index.py    # data/ PDF → FAISS 인덱스 생성
├── data/                       # RAG용 PDF
├── reports/                    # 생성 보고서(md/pdf)
├── design-deliverables.md
├── UPGRADE_REPORT.md           # 시스템 고도화 및 임베딩 업그레이드 이력
└── semiconductor_ai_investment_flowchart_v3.svg
```

## Contributors

- AI 1반: 김주환, 방다원, 지다은, 한상윤
  - 김주환: 파이프라인 설계, pdf 전처리 및 임베딩 구현, Master Agent 구현
  - 방다원: 아키텍처 설계, Master Agent 구현, 기술 요약 Agent 구현
  - 한상윤: 아키텍처 설계, Master Agent 구현, 시장성 평가 Agent 구현
  - 지다은: 아키텍처 설계, Master Agent 구현, 경쟁사 평가 Agent 구현