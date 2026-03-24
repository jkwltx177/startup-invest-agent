# Semiconductor AI Startup Investment Evaluation Agent

반도체·AI 도메인 스타트업을 대상으로, RAG와 멀티 에이전트 파이프라인으로 **후보 발굴 → 순차 심사 → 투자/보류 판단 → 보고서**까지 이어지는 프로젝트입니다.

## 0. Architecture

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
└── semiconductor_ai_investment_flowchart_v3.svg
```

## 7. 시작하기

1. **환경 변수**  
   프로젝트 루트에 `.env`를 두고, 실행에 필요한 키를 설정합니다.  
   (예: LLM, 선택적 웹 검색·Hugging Face 캐시 등 — `scripts/run_full.py` 상단 주석 참고)
2. **의존성**  
   `uv sync` 또는 `pip install -e .` 등 `pyproject.toml` 기준으로 설치합니다.
3. **RAG 인덱스**  
   `data/`에 PDF를 넣은 뒤 `uv run python scripts/build_faiss_index.py`로 FAISS 인덱스를 만들 수 있습니다. (없으면 실행 시 생성 시도)
4. **실행**  
   ```bash
   uv run python scripts/run_full.py
   ```  
   또는 질의를 인자로:  
   `uv run python scripts/run_full.py "질의 내용"`

## 8. 기타

- 상세 설계·용어는 `design-deliverables.md`, `agents_detail.md` 등을 참고하세요.
- 예전 문서에 있던 “다중 루프 Corrective RAG 자동 3회” 같은 설명은 **현재 그래프와 다를 수 있습니다.** 실제 동작은 `src/graph/workflow.py` 기준입니다.

## Contributors

- AI 1반: 김주환, 방다원, 지다은, 한상윤
