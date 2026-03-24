# RAG 실습 - 설계 산출물

AI 1반 김주환, 방다원, 지다은, 한상윤

# A. Domain 선정

- Semiconductor
    - 반도체 관련 인공지능 솔루션 개발 or AI 반도체 설계하는 팹리스 스타트업

# B. 설계 : 에이전트 정의, RAG 적용 대상, 선정한 Embedding 모델

본 시스템은 반도체 도메인을 중심으로 AI 스타트업의 투자 가치를 분석하기 위한 **Hierarchical Agentic RAG 기반 멀티 에이전트 구조**로 설계된다. 사용자 질의를 입력으로 받아 Master Agent(Supervisor)가 전체 흐름을 제어하며, 하위 에이전트들은 서로 직접 연결되지 않고 독립적으로 분석을 수행한다. 이후 Master Agent가 결과를 집계·보정하고 최종 투자 판단과 보고서를 생성하는 구조이다.

---

# 시스템 개요

본 시스템은 단일 LLM이 아닌 역할이 분리된 에이전트 구조를 통해 분석의 신뢰성과 해석 가능성을 확보하는 것을 목표로 한다. 각 에이전트는 특정 목적에 최적화된 분석을 수행하며, 모든 결과는 중앙에서 통합된다.

- Hierarchical 구조: Master Agent가 전체 흐름을 제어
- Multi-Agent 구조: 기능별 역할 분리
- Agentic 구조: 각 에이전트가 목적 기반으로 독립 수행
- Corrective 구조: 필요한 단계에서만 재수행 (최대 3회)
- Adaptive 구조: 상황에 따라 재검색 및 보정 수행

---

# RAG 적용 설계

본 시스템은 최소 1개 이상의 에이전트에 RAG를 적용해야 한다는 조건을 충족하며, 핵심 분석 단계에 RAG를 적용하여 정보 신뢰도를 확보한다.

RAG 적용 대상은 다음과 같다.

- 스타트업 탐색 에이전트
- 기술 요약 에이전트
- 시장성 평가 에이전트

문서 구성은 다음 제약을 따른다.

- 최대 4개 문서 사용
- 문서당 50페이지 이하
- 총 200페이지 이내

문서는 LLM 기반 도구(Consensus, Scholar GPT 등)를 활용하여 준비하며, Vector DB에 chunk 단위로 저장 후 semantic retrieval을 수행한다. 이를 통해 단순 LLM 추론이 아닌 **근거 기반 분석**을 수행하도록 설계한다.

# 에이전트 구조 정의

각 에이전트는 Master Agent 아래에서 독립적으로 실행되며, 서로 직접적인 데이터 전달 없이 공통 입력 기반으로 동작한다.

| 에이전트 | 핵심 기능 | 출력 정보 | Loop 조건 및 전략 |
| --- | --- | --- | --- |
| **Startup Discovery Agent**(스타트업 탐색)
 | - Query 이해 및 키워드 확장 (AI chip, EDA, Fab AI 등)- RAG 기반 기업 검색 (리포트, 기사, DB 활용)- Entity Extraction (기업명, 기술 분야, 투자 단계)- Domain Filtering (반도체 관련성 score 기반)- Ranking 및 Top-K 선정 | - 스타트업 리스트- 기술 분야 태그- 기본 기업 정보 | - 후보 수 부족/과다- 반도체 도메인 불일치→ Query rewrite 후 재검색(최대 3회) |
| **Technology Summary Agent**(기술 요약)
 | - RAG 기반 문서 retrieval (논문, 홈페이지, 기술 문서)- Technical Parsing (모델 구조, 알고리즘)- Problem-Solution Mapping (해결 문제 정의)- Innovation Detection (기존 대비 개선점)- Strength / Weakness 분석 | - 기술 유형- 핵심 기술 메커니즘- 적용 영역- 기술 차별성 | - 핵심 기술 누락- 문서 간 정보 충돌→ re-retrieval / re-ranking(최대 3회) |
| **Market Evaluation Agent**(시장성 평가) | - 산업 리포트 RAG 검색- TAM / SAM / SOM 추출- CAGR 기반 성장 분석- 시장 세그먼트 매핑- 기술-수요 정합성 평가 | - 시장 규모- 성장률- 시장 위치- 투자 매력도 | - 시장 범위 과도/협소- 수치 불일치→ query refinement(최대 3회) |
| **Competitor Comparison Agent**(경쟁 분석) | - 경쟁사 식별- Positioning 분석 (기술 vs 점유율)- 차별성 분석- 진입장벽 평가- 리스크 식별 | - 경쟁사 리스트- 포지셔닝- 차별성- 리스크 요인 | - 경쟁사 정의 불명확→ 후보 재선정(최대 2회) |
| **Investment Decision Agent**(Supervisor)

**핵심역할**
중앙 의사결정 및 투자 판단 | - Feature Normalization- Scoring System 구축- Weighted Aggregation- Threshold 기반 판단 | - 최종 점수- 투자 / 보류 결과 | - Loop 없음 (단일 실행)- 불확실성은 리스크 반영 |
| **Report Generation Agent**(보고서 생성) | - 결과 통합- 논리적 구조화- 근거 연결- 자연어 생성 | - 최종 투자 보고서 | - Loop 없음 (단일 실행) |

# Loop 기반 Corrective 설계

본 시스템은 전체 파이프라인을 반복하지 않고, **필요한 단계에서만 제한적으로 loop를 수행**한다.

- RAG 기반 단계에서만 최대 3회 반복
- 품질 기준 충족 시 즉시 종료
- 전체 재실행이 아닌 해당 단계만 재수행
- 경쟁사 분석은 최대 2회로 제한

이를 통해 검색 품질과 실행 효율성을 동시에 확보한다.

---

# Embedding 모델 선정

본 시스템은 경제성과 성능을 고려하여 오픈소스 임베딩 모델을 적용하며, **BAAI의 bge-m3 모델을 최종 채택**한다.

선정 이유는 다음과 같다.

- 반도체 도메인은 영어 기술 문서 + 한국어 리포트 혼합 환경이므로
→ **multilingual 성능이 필수적**
- bge-m3는 MTEB benchmark에서 상위권 성능을 보이며
→ **retrieval 정확도가 매우 안정적**
- 다양한 문서 타입(논문, 리포트, 웹 데이터)에 대해
→ **semantic similarity 기반 검색 성능이 우수**

검증 기준은 다음과 같다.

- HuggingFace MTEB (eng + kor)
- AutoRAG 한국어 임베딩 benchmark
- Allganize RAG evaluation dataset

---

# 최종 투자 판단 구조

투자 판단은 다음 세 가지 기준을 기반으로 수행된다.

- 평가 기준 구조 설계 → 분리 이유 : 반도체 산업 세분화로 스타트업 유형이 2가지 이상 존재한다고 판단
    
    ① 반도체 AI 솔루션 스타트업 → 공정이나 설계, 분석 자동화에 대한 AI 솔루션 제공
    
    ② AI 반도체 스타트업 (팹리스) → AI 반도체에 대한 공정/설계 기술력
    
    > 
    > 
    > 
    > ① Scorecard 기본 > 60점
    > 
    > ② Semiconductor 특화 > 25점
    > 
    > ③ 산업 트렌드 적합성 > 15점
    > 
    - Scorecard Method 기반 항목 (Subtotal = 60%)
        
        
        | 항목 | 비중 | 평가 방식 | Threshold 적용 여부 | Threshold 기준 | 평가 포인트 | 항목의 의의 |
        | --- | --- | --- | --- | --- | --- | --- |
        | 창업자(Owner) | 15% | 1~5 척도 | O | 3 이상 | fabless / AI chip 경험 | 팀 역량 |
        | 시장성 | 15% | 1~5 척도 | O | 3 이상 | AI 반도체 시장 | 시장 크기 |
        | 제품/기술력 | 10% | 1~5 척도 | O | 3 이상 | PoC / prototype | 기술 실행력 |
        | 경쟁 우위 | 8% | 1~5 척도 | X | - | GPU 대비 효율 | 진입장벽 |
        | 실적 | 6% | 1~5 척도 | X | - | design win | 시장 검증 |
        | 투자조건 | 6% | 1~5 척도 | X | - | funding stage | 투자 리스크 |
    - Semiconductor 특화 항목 (Subtotal = 25%)
        
        
        | 항목 | 비중 | 평가 방식 | Threshold 적용 여부 | Threshold 기준 | 평가 포인트 | 항목의 의의 |
        | --- | --- | --- | --- | --- | --- | --- |
        | 반도체 기술 차별성 | 8% | 1~5 척도 | O | 3 이상 | NPU / AI accelerator | 핵심 경쟁력 |
        | 제품 단계 | 5% | 1~5 척도 | O | 2 이상 | Tape-out | 실행력 |
        | 데이터 접근성 | 4% | 1~5 척도 | X | - | fab 데이터 | AI 성능 핵심 |
        | 생태계 적합성 | 4% | 1~5 척도 | X | - | SDK / SW stack | 시장 진입 |
        | IP / 특허 | 4% | 1~5 척도 | X | - | patent | 장기 경쟁력 |
    - 산업 트렌드 적합성 (Subtotal = 15%)
        
        
        | 항목 | 비중 | 평가 방식 | Threshold 적용 여부 | Threshold 기준 | 평가 포인트 | 항목의 의의 |
        | --- | --- | --- | --- | --- | --- | --- |
        | 산업 트렌드 적합성 | 5% | 1~5 척도 | X | - | DRAM/NAND/HBM | 타이밍 |
        | 기술 적용 영역 | 4% | 1~5 척도 | X | - | 설계 vs 공정 | 시장 크기 |
        | 고객 산업 적합성 | 3% | 1~5 척도 | X | - | memory / foundry | 수요 |
        | 성장성 | 3% | 1~5 척도 | X | - | roadmap | 확장성 |

각 평가 항목을 척도 기반으로 점수화한 뒤, 창업자 역량·시장성·기술력·반도체 기술 차별성·제품 단계에 대한 최소 기준(Gate)을 먼저 확인하고, 이를 통과한 경우 가중합 점수를 계산한다. 이후 최종 점수가 설정된 임계값 이상이면 **투자**, 미만이면 **보류**로 판단한다. (각 척도에 대한 상세한 기준 설계가 추후 필요하다.)

---

# [D. 그래프 설계(안)](https://www.notion.so/f0fb45fc1bdb829abe64019045123f48?pvs=21) : State, Graph 흐름

**State**

```json
class GraphState(TypedDict):
    # ── [입력 및 흐름 제어] ────────────────────────────────────────────────
    # 시스템의 시작점이자 에이전트들이 참조할 핵심 가이드라인
    question: Annotated[str, "사용자가 입력한 최초의 검색 또는 분석 질의어 (수정 금지)"]
    target_domain: Annotated[str, "분석 대상 산업 분야 (예: 생성형 AI, 차세대 전력 반도체 등)"]

    next_agent: Annotated[str, "상태 전이(State Transition)를 결정하는 필드. 다음에 실행될 노드 이름"]
    active_agents: Annotated[List[str], "현재 병렬로 실행 중이거나 실행 대기 중인 워커 에이전트 목록"]

    # ── [Worker 결과 (누적: operator.add)] ────────────────────────────────
    # 여러 에이전트가 각자의 결과를 List에 추가(Append)하여 전체 데이터를 형성함
    startup_candidates: Annotated[
        List[StartupProfile],
        operator.add,  # 여러 검색 에이전트가 찾아낸 후보군을 하나의 리스트로 통합
    ]

    validation_results: Annotated[
        List[ValidationResult],
        operator.add,  # 각 스타트업에 대한 검증(점수, 통과여부) 결과를 순차적으로 누적
    ]

    tech_summaries: Annotated[
        List[TechSummary],
        operator.add,  # 기술성숙도(TRL), 특허수 등 심층 기술 분석 데이터를 스타트업별로 축적
    ]

    market_analyses: Annotated[
        List[MarketAnalysis],
        operator.add,  # 시장 규모(TAM/SAM) 및 경쟁사 분석 데이터를 누적하여 비교 근거 마련
    ]

    # ── [Judge & Loop 제어] ───────────────────────────────────────────────
    # 워크플로우의 품질을 관리하고 무한 루프를 방지하는 통제실 역할
    judge_history: Annotated[
        List[JudgeVerdict],
        operator.add,  # 매 회차(Iteration)마다 Judge가 내린 판단 근거를 기록 (감사 추적용)
    ]

    iteration_count: Annotated[int, "현재 재평가 루프 횟수. 최대 반복 횟수(Max Iteration) 도달 체크용"]

    is_done: Annotated[bool, "파이프라인 종료 플래그. True일 경우 최종 결과 생성 노드로 진입"]

    # ── [최종 출력 (덮어쓰기)] ──────────────────────────────────────────────
    # 모든 분석이 끝난 후, 최종적으로 사용자에게 전달될 결과물
    selected_startup: Annotated[Optional[str], "모든 검증을 통과하여 최종 선정된 대표 스타트업 명칭"]
    final_report: Annotated[Optional[str], "분석된 모든 데이터를 종합하여 작성된 마크다운 형식의 투자 분석 보고서"]\
```

**Graph 흐름**

![image.png](attachment:12f3fa7e-004e-4a43-b10b-bdd8ad25f927:image.png)

![image.png](attachment:696ae4b9-d95d-4d5d-9677-29c9b58892f0:image.png)

# E. 투자 보고서 : 보고서 목차(초안)

## AI 스타트업 투자 심사 보고서 목차

## 0. Executive Summary

투자구조, 기업현황, 투자포인트 및 투자 수익성에 대하여 요약

- (투자구조) 투자재원, 방식, 금액, 지분율 및 기업가치(Pre/Post)
- (기업현황) 회사개요 및 핵심 AI 기술 스택(Foundation Model, Agentic AI 등) 요약
- (투자포인트) Bessemer Checklist 기준 핵심 강점(성장성, 자본 효율성, 기술적 해자)
- (회수 및 수익성) 예상 Exit 시나리오(M&A/IPO) 및 회수 예상 시기/수익률(Multiple, IRR)

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
- **AI 거버넌스 및 윤리 정책 수립 현황**

### 1-5. 주요 주주 및 자본금 변동 내역

### 1-6. 주식관련 사채 및 Stock Option 발행 현황

### 1-7. 인프라 및 주요 관계회사 현황

- **확보된 연산 자원(GPU 클러스터 등) 및 독점 데이터 파이프라인 현황**

### 1-8. 기타 사항

## 2. 투자구조

### 2-1. 투자 전 자본금 및 주주 현황

### 2-2. 투자 내역 및 상세 조건

- 투자금액, 방식, 인수주식, 단가 및 기업가치
- (상세조건) 만기, 상환/전환 조건, Tag-along/Drag-along, Refixing 조건 등

### 2-3. 조합의 주목적 투자 분야 부합 여부

### 2-4. 투자금 사용 용도 및 관리 방안

- 인재 영입, GPU 인프라 확충, 데이터 확보 비용 등 구체적 명시

## 3. 재무 현황 및 Bessemer 지표 분석

### 3-1. 요약 재무 현황

- 과거 1개년 ~ 현재 최근 분기 재무상태표 및 손익계산서

### 3-2. Bessemer 효율성 지표 분석

- **효율성 점수(Efficiency Score)** 측정
- **현금 전환 점수(Cash Conversion Score)** 분석
- **성장 내구력(Growth Endurance) 및 NRR(순매출 유지율)**

### 3-3. 매출 성장 추이 및 수익성 분석

- 운전자본 추이 및 현금 소진율(Burn Rate) 분석

### 3-4. 분기별/월별 매출 현황 및 현금 흐름 추정

## 4. 사업 및 시장 현황 (AI 특화 분석)

### 4-1. 기술 및 솔루션 심층 분석

- AI 모델 독창성, 데이터 소스 및 품질, R&D 로드맵
- **에이전트형 AI(Agentic AI)의 자율성 및 워크플로우 실행 능력 평가**

### 4-2. 사업 현황 및 마케팅 전략

- 제품별 매출 비중, 주요 매출처 분석
- **AI 도입에 따른 고객 업무 효율 개선 지표(ROI) 제시**

### 4-3. 시장(Value Chain) 및 경쟁 현황 분석

- 시장 규모(TAM/SAM/SOM) 및 성장 전망
- **데이터 인프라 및 클라우드 서비스와의 밸류체인 통합성**

### 4-4. 차별화 경쟁력 및 진입 장벽 (AI Moat)

- **데이터 해자:** 학습 데이터의 희소성 및 데이터 플라이휠 효과 분석
- **전환 비용:** 고객 시스템과의 깊은 통합 및 고착화(Lock-in) 전략

## 5. 매출 및 손익 추정

### 5-1. 회사 제시 추정 손익계산서 및 근거

### 5-2. 투자사 보수적 추정 손익계산서 및 민감도 분석

- 시장 변동 및 모델 컴퓨팅 비용 상승 시나리오 반영

## 6. 밸류에이션 및 투자 수익성 분석

### 6-1. 일반 가정

- Full Dilution 기준 주식수, 예상 공모가 및 시점

### 6-2. 미래 기업 가치 추정 (Multiple Value)

- 유사 AI 상장사 및 최근 유니콘 라운드 비교
- 회수 시기별 수익률 분석 (Multiple, IRR)

### 6-3. 현재 기업 가치 평가 (Scorecard Method 적용)

- **Bill Payne 방식 가중치 적용:** 팀 역량(30%), 시장 규모(25%), 기술 혁신성(15-25%) 등
- 지역/섹터 평균 대비 조정 계수 산출 및 단가 적정성 검토

## 7. 종합 투자 검토 의견

### 7-1. 긍정적 측면 (Bessemer Checklist 기준)

- 기술적 우위, 지표 우수성, 시장 선점 가능성

### 7-2. 리스크 요인 및 대응 방안

- 기술적 한계(환각 현황 등), 데이터 저작권 리스크, 규제 대응 역량

### 7-3. 종합 의견

- 투자 승인 여부 및 사후 관리 전략

## 8. (별첨) Reference 및 기술 실사 자료

- 기술 실사(Technical Due Diligence) 결과 요약
- 주요 데이터셋 인벤토리 및 라이선스 현황

---

# 에이전트 개발 과정