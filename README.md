# 반도체 AI 스타트업 투자 평가 에이전트

> LangGraph 기반 멀티에이전트 투자 심사 자동화 시스템

(실제 산출물은 output의 invest_FuriosaAi로 시나리오는 성공시나리오.txt로 확인할 수 있다.)

---

## 프로젝트 개요

반도체 AI 스타트업을 대상으로 **발굴 → 기술/시장/경쟁사 분석 → 투자 결정 → 보고서 생성**까지의 투자 심사 파이프라인을 자동화하는 멀티에이전트 시스템이다.

| 항목 | 내용 |
|------|------|
| **프레임워크** | LangGraph (StateGraph + MemorySaver) |
| **LLM** | GPT-4o-mini (structured output + function calling) |
| **임베딩** | BAAI/bge-m3 (CPU) |
| **벡터 DB** | FAISS (로컬 인덱스 `.cache/faiss_index_bge-m3/`) |
| **웹 검색** | Tavily (advanced depth) |
| **체크포인터** | MemorySaver (in-memory HITL 지원) |
| **보고서** | PDF 생성 (WeasyPrint) |

**핵심 특징**
- 10개 에이전트 + 5개 HITL 체크포인트
- FAISS 캐시 HIT 시 웹 검색 비용 절감
- Fan-out/Fan-in 병렬 분석 (기술·시장·경쟁사)
- 투자 스코어카드 3개 영역 × 17개 지표
- 리플렉션 기반 보고서 품질 검증

---

## 시스템 아키텍처

### 전체 흐름 다이어그램

```
START
  │
  ▼
[orchestrator] ──(direct)──────────────────────────────▶ END
  │ (pipeline)
  ▼
[supervisor] ◀─────────────────────────────────────────┐
  │                                                     │
  ├─(discovery)──▶ [discovery] ──────────────────────▶ ┤ (fan-in)
  │                                                     │
  ├─(mini_supervisor)─▶ [mini_supervisor]              │
  │                         │ Send × 3                  │
  │                    ┌────┼────┐                      │
  │                    ▼    ▼    ▼                      │
  │             [tech] [market] [competitor]            │
  │                    └────┬────┘                      │
  │                         └──────────────────────────▶┘
  │
  ├─(judge_loop)──▶ [judge_loop]
  │                    ├─(passed)────────────────────▶ [decision]
  │                    └─(failed)────────────────────▶ [supervisor]
  │
  └─(decision)───▶ [decision]
                      ├─(invest)──────────────────────▶ [report_gen] ──▶ END
                      ├─(hold + 남은 후보)─────────────▶ [supervisor]
                      └─(hold + 후보 소진)─────────────▶ END
```

### Supervisor 패턴 설명

`Supervisor`는 **조건 기반 라우터**로, 어떤 에이전트를 다음에 실행할지 결정한다.

```
supervisor 진입 시 결정 트리:
1. hold + 후보 풀 남음          → pool_offset 증가 → mini_supervisor (다음 후보)
2. discovery 미완료              → discovery
3. judge_retry_target 있음       → retry_agents 세팅 → mini_supervisor (부분 재실행)
4. 분석 결과 미완                → mini_supervisor (전체 fan-out)
5. 분석 완료 + judge 미통과      → judge_loop
6. 분석 완료 + judge 통과        → decision
7. iteration_count >= 10        → decision (강제 종료)
```

각 에이전트 진입 전에 `agent_queries` 딕셔너리에 에이전트별 **특화 쿼리**를 재작성한다.

### Mini-Supervisor & 에이전트 구조

**설계 의도:**
MiniSupervisor는 원래 tech_summary · market_eval · competitor 세 에이전트의
실행 진행 상황을 추적하고, 개별 에이전트 오류·타임아웃 발생 시 부분 재시도를 자율 결정하는
**서브 오케스트레이터**로 설계되었다.
Supervisor(상위)는 전체 워크플로우 흐름만 결정하고,
MiniSupervisor가 병렬 분석 묶음 내부의 상태 관리를 담당하는 계층 분리가 의도였다.

그러나 LangGraph에서 노드 `__call__` 내부에서 `Send`를 반환하는 것이 지원되지 않아,
fan-out 로직을 `workflow.py`의 `add_conditional_edges` 라우터 함수로 이전할 수밖에 없었다.
결과적으로 MiniSupervisor 노드 자체는 상태를 그대로 통과시키는 **패스스루**가 되었다.

`MiniSupervisor`는 **패스스루 노드**다. 실제 fan-out은 `workflow.py`의 `mini_supervisor_router` 함수가 `Send` 객체를 반환해서 수행한다.

```python
# workflow.py
def mini_supervisor_router(state):
    retry_agents = state.get("retry_agents", [])
    if retry_agents:                          # judge 재시도: 지정 에이전트만
        return [Send(a, state) for a in retry_agents if a in valid]
    return [                                  # 정상: 전체 병렬
        Send("tech_summary", state),
        Send("market_eval", state),
        Send("competitor", state),
    ]
```

> ⚠️ `Send`는 노드 `__call__`이 아니라 `add_conditional_edges`의 라우터 함수에서 반환해야 한다.

### 캐싱 전략

**Cache HIT 조건:**
```
FAISS score >= 0.72 인 청크가 3개 이상 → cache_hit = True
```

| 에이전트 | Cache HIT | Cache MISS |
|---------|-----------|------------|
| tech_summary | vector 검색만 | vector + 웹 검색 |
| competitor | vector 검색만 | vector + 웹 검색 |
| market_eval | — | 항상 vector + 웹 검색 |
| discovery | — | 항상 웹 검색 |

캐시 HIT 여부는 `state.get("_cache_hit_flags", {})` 로 전달된다 (GraphState 외부 임시 필드).
Judge가 `re_retrieve` 전략으로 재시도 시 플래그를 초기화해 재검색을 강제한다.

**캐시 설계 의도:**
에이전트가 특정 스타트업 분석을 마치면, 그 결과(청크 단위 텍스트)를 FAISS 인덱스에 역으로 저장(write-back)하는 구조를 설계했다.
투자 심사 특성상 같은 기업을 반복 검토하는 일이 잦은데, 이미 한 번 조사한 결과를 버리는 것은 낭비다.
재조사 시 웹 검색 없이 벡터 검색만으로 분석을 완료할 수 있도록 하는 것이 목표였다.

그러나 현재 구현에서 FAISS 인덱스는 **읽기 전용**으로만 사용되고,
분석 결과를 인덱스에 저장하는 write-back 파이프라인은 미구현 상태다.

> **S3**: 현재 미구현. 로컬 FAISS 인덱스만 사용 (`.cache/faiss_index_bge-m3/`).

---

## HITL 체크포인트

| CP | 노드 | 발동 조건 | 블로킹 | 선택지 |
|----|------|----------|--------|-------|
| **CP-1** | orchestrator | 도메인 분류 신뢰도 < 0.5 | ✅ | 계속 / 중단 |
| **CP-2** | discovery | 후보 발굴 완료 시 | ✅ | 후보 선택 / 재검색 |
| **CP-3** | judge_loop | judge 2회 연속 실패 | ✅ | 강제 통과 / 재시작 / 현재 데이터로 진행 |
| **CP-3.5** | decision | 스코어링 직전 분석 데이터 확인 | ✅ | 스코어링 진행 / 재분석 |
| **CP-4** | decision | 투자 결정 완료 (invest일 때만) | ✅ | 보고서 생성 / 재검토 |

**CP-4 주의**: `overall_decision == "hold"` 이면 CP-4 프롬프트 자체가 스킵되고 보고서 없이 END로 라우팅된다.

**HITL 재개 루프 (`src/main.py`):**
```python
while True:
    result = await app.ainvoke(input_data, thread)
    if "__interrupt__" in result:
        # 체크포인트 메시지 출력 및 사용자 입력 수집
        input_data = Command(resume=user_input)
        continue
    break
```

---

## GraphState 설계

### 서브 타입 정의 (`src/schema/models.py`)

| 타입 | 용도 |
|------|------|
| `StartupProfile` | 스타트업 기본 정보 (name, domain, stage, description, relevance_score) |
| `TechSummary` | 기술 분석 결과 (tech_type, core_mechanism, differentiation, strengths, weaknesses, confidence_score) |
| `MarketAnalysis` | 시장 분석 결과 (market_size, growth_rate, market_position, investment_attractiveness) |
| `CompetitorProfile` | 경쟁사 비교 결과 (competitor_name, tech_gap_summary, market_share_pct, funding_total_usd) |
| `ValidationResult` | 투자 결정 (score 0-100, investment_category, scorecard_breakdown, investment_risk) |
| `JudgeVerdict` | Judge 판정 (passed, failed_criteria, retry_strategy, target_agents) |
| `HITLRequest` | HITL 체크포인트 요청 구조 |
| `HITLRecord` | HITL 이력 기록 |

### 전체 필드 (overwrite vs operator.add)

| 필드 | 타입 | 병합 방식 | 설명 |
|------|------|----------|------|
| `question` | str | overwrite | 사용자 질문 |
| `target_domain` | str | overwrite | 분석 도메인 |
| `route_type` | str | overwrite | "direct" / "pipeline" |
| `direct_answer` | Optional[str] | overwrite | direct 라우트 시 즉시 응답 |
| `detected_domain` | str | overwrite | Orchestrator 감지 도메인 |
| `next_agent` | str | overwrite | Supervisor가 설정하는 다음 노드 |
| `agent_queries` | Dict[str, str] | overwrite | 에이전트별 특화 쿼리 |
| `startup_candidates` | List[StartupProfile] | **overwrite** | 현재 평가 중인 후보 배치 |
| `candidate_pool` | List[StartupProfile] | **overwrite** | 발굴된 전체 후보 풀 |
| `pool_offset` | int | overwrite | 다음 평가 후보 인덱스 |
| `tech_summaries` | List[TechSummary] | **operator.add** | 기술 분석 누적 |
| `market_analyses` | List[MarketAnalysis] | **operator.add** | 시장 분석 누적 |
| `competitor_profiles` | List[CompetitorProfile] | **operator.add** | 경쟁사 분석 누적 |
| `validation_results` | List[ValidationResult] | **operator.add** | 투자 결정 누적 |
| `judge_history` | List[JudgeVerdict] | **operator.add** | Judge 판정 이력 |
| `judge_iteration` | int | overwrite | Judge 시도 횟수 |
| `judge_passed` | bool | overwrite | Judge 통과 여부 |
| `judge_retry_target` | List[str] | overwrite | 재시도 대상 에이전트 |
| `retry_agents` | List[str] | overwrite | mini_supervisor_router 전달용 |
| `iteration_count` | int | overwrite | 전체 루프 카운터 (max 10) |
| `is_done` | bool | overwrite | 워크플로우 완료 플래그 |
| `hitl_enabled` | bool | overwrite | HITL 활성화 여부 |
| `hitl_records` | List[HITLRecord] | **operator.add** | HITL 이력 |
| `investment_decision` | Optional[str] | overwrite | "invest" / "hold" |
| `selected_startup` | Optional[str] | overwrite | 선택된 스타트업 이름 |
| `final_report` | Optional[str] | overwrite | 마크다운 보고서 |
| `report_pdf_path` | Optional[str] | overwrite | 생성된 PDF 경로 |
| `logs` | List[str] | **operator.add** | 실행 로그 누적 |

---

## 에이전트별 역할

### Startup Discovery (`src/agents/discovery.py`)

발굴 대상 도메인(HBM, EDA, Fab AI 등)에 대해 웹 검색 3건 + FAISS 벡터 검색(k=5)을 수행한다.

**필터 파이프라인:**
1. LLM이 문맥에서 후보 추출
2. `relevance_score >= 0.6` 필터
3. 대기업 · 후기 단계 스타트업 제외
4. **CP-2**: 사용자가 첫 번째 평가 후보 선택

**출력:** `candidate_pool` (전체) + `startup_candidates` (선택된 1개) + `pool_offset=1`

---

### Technology Summary (`src/agents/tech_summary.py`)

FAISS 벡터 검색(k=5) + 캐시 MISS 시 웹 검색(상위 2개 후보 × 2건)을 수행한다.

**분석 항목:** `tech_type`, `core_mechanism`, `application_area`, `differentiation`, `strengths`, `weaknesses`, `confidence_score`

- Cache HIT → `confidence_score = 0.75`
- Cache MISS → `confidence_score = 0.55`

---

### Market Evaluation (`src/agents/market_eval.py`)

FAISS(k=5) + 웹 검색(상위 3개 후보 × 2건 + 글로벌 트렌드 2건)을 항상 수행한다.

**분석 항목:** `market_size` (TAM/SAM/SOM), `growth_rate` (CAGR), `market_position`, `investment_attractiveness`

---

### Competitor Comparison (`src/agents/competitor.py`)

후보 수에 따라 분석 모드가 분기된다.

| 조건 | 모드 | 쿼리 방향 | 프롬프트 |
|------|------|----------|---------|
| N ≥ 2 | 스타트업 간 상호 비교 | 각 스타트업의 기술·펀딩 정보 검색 | `_CROSS_STARTUP_PROMPT` |
| N = 1 | 외부 경쟁사 탐색 | 경쟁사·rival 키워드 검색 | `_COMPETITOR_PROMPT` |

N ≥ 2 모드에서는 후처리 필터로 `competitor_name`이 후보 목록 외 이름이면 제거한다 (대기업 유입 차단).

---

### Report Generation (`src/agents/report_gen.py`)

4개 섹션을 `asyncio.gather()`로 **병렬 생성**한다.

| 섹션 | 내용 |
|------|------|
| Executive Summary | 투자 구조, 기업 개요, 투자 포인트, Exit 시나리오 |
| 회사 현황 | 연혁, 사업 내용, 핵심 인력, GPU 인프라 |
| 사업 및 시장 현황 | 기술 심층 분석, TAM/SAM/SOM, AI Moat |
| 종합 투자 검토 의견 | Bessemer Checklist, 리스크, 최종 권고 |

경쟁사 비교표 및 시장 점유율 바 차트도 포함된다.
생성 후 LLM 리플렉션으로 품질 점수(0-10)와 할루시네이션 여부를 검증한다.

**HOLD 결정 시**: `report_gen` 노드 자체를 타지 않고 END로 바로 라우팅된다.

---

### 회고
**우리가 지향했던 구조 (The Ideal)**

- 명확한 책임 전담 (Supervisor-Minivisor): 상위 Supervisor는 전체 흐름을 관장하고, Mini-Supervisor는 특정 도메인(기술/시장/경쟁사)의 세부 실행과 오류 복구를 전담하는 계층적 오케스트레이션을 목표로 했습니다.

- 정교한 HITL(Human-In-The-Loop): 중요한 결정 길목마다 사용자에게 잦은 질문을 던지고 피드백을 수용하여, 자율 에이전트의 불확실성을 제거하고 업무의 정확도를 극대화하고자 했습니다.

- 서브 에이전트의 완결성: 각 에이전트가 부여받은 전문 영역(기술 분석, 시장 평가 등)에 대해 독립적이고 완벽한 결과물을 도출하는 구조를 설계했습니다.

- 캐싱을 통한 비용 절감: 이미 조사한 보고서 내용이나 검색 결과는 벡터 DB에 캐싱하여, 동일하거나 유사한 스타트업 검토 시 API 호출 비용과 시간을 획기적으로 절감하려 했습니다.

**구현의 한계와 아쉬운 점 (The Reality)**

- Mini-Supervisor의 역할 약화: LangGraph의 노드 내부에서 Send 객체를 반환하는 방식의 제약으로 인해, Mini-Supervisor가 자율적으로 하위 에이전트를 제어하기보다는 상태를 전달하는 패스스루(Pass-through) 노드에 그친 점이 아쉽습니다.

- 반쪽짜리 캐시 전략과 미완의 선순환: 현재 시스템은 기존에 생성된 인덱스를 '읽는' 기능만 수행합니다.

의도한 목적: 당초 Write-back(역저장) 파이프라인을 설계한 이유는 에이전트가 공들여 분석한 고부가가치 데이터를 자산화하기 위함이었습니다. 웹 검색으로 얻은 단편적인 정보가 아니라, LLM이 정제한 '심층 분석 결과'를 다시 지식 베이스(DB)에 축적함으로써, 다음에 같은 기업이나 유사 도메인을 조사할 때 별도의 검색 비용 없이 즉각적으로 고품질의 답변을 내놓는 **지능형 데이터 플라이휠**을 구축하고자 했습니다.

결과: 하지만 시간 관계상 분석 결과를 인덱싱하는 자동화 로직을 완성하지 못했고, 결과적으로 데이터가 쌓이며 시스템이 똑똑해지는 선순환 구조를 끝까지 보여주지 못한 점이 가장 큰 과제로 남았습니다.

---

## Contributors

- AI 1반: 김주환, 방다원, 지다은, 한상윤
  - 김주환: 파이프라인 설계, pdf 전처리 및 임베딩 구현, Master Agent 구현
  - 방다원: 아키텍처 설계, Master Agent 구현, 기술 요약 Agent 구현
  - 한상윤: 아키텍처 설계, Master Agent 구현, 시장성 평가 Agent 구현
  - 지다은: 아키텍처 설계, Master Agent 구현, 경쟁사 평가 Agent 구현
