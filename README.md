# Semiconductor AI Startup Investment Evaluation Agent (Hierarchical Agentic RAG)

본 프로젝트는 반도체 도메인을 중심으로 AI 스타트업의 투자 가치를 분석하기 위한 **Hierarchical Agentic RAG 기반 멀티 에이전트 시스템**입니다.

## 0. Architecture
![System Architecture](./semiconductor_ai_investment_flowchart_v3.svg)

## 1. Overview
- **Domain**: Semiconductor (AI Chip, EDA, Fab AI, etc.)
- **Method**: Hierarchical Multi-Agent System + Agentic RAG
- **Core Goal**: 신뢰성 있는 데이터를 바탕으로 스타트업의 기술력, 시장성, 경쟁력을 종합 평가하여 투자 보고서 생성

## 2. Agent Structure
- **Supervisor (Master Agent)**: 전체 흐름 제어, 의도 파악 및 Task Orchestration, 최종 Scorecard 기반 가중치 점수 산출 및 투자/보류 판단.
- **Startup Discovery Agent**: RAG 및 웹 검색을 통한 후보 기업 발굴 및 기본 정보 추출.
- **Technology Summary Agent**: 기술 문서(논문, IR 등) RAG 분석을 통한 기술적 해자(Moat) 및 차별성 평가.
- **Market Evaluation Agent**: 산업 리포트 RAG 분석을 통한 TAM/SAM/SOM 및 시장 성장성 분석.
- **Competitor Comparison Agent**: 경쟁사 식별 및 포지셔닝 분석.
- **Report Generation Agent**: 분석된 모든 데이터를 종합하여 마크다운 형식의 투자 분석 보고서 생성.

## 3. Tech Stack 
| Category   | Details                        |
|------------|--------------------------------|
| Framework  | LangGraph, LangChain, Python   |
| LLM        | GPT-4o, GPT-4o-mini            |
| Retrieval  | FAISS (Vector DB)              |
| Embedding  | BAAI/bge-m3 (Multilingual)     |
| Search     | Tavily (Web Search)            |

## 4. Directory Structure
```text
├── src/
│   ├── main.py             # Entry point
│   ├── graph/              # LangGraph Workflow & State
│   ├── agents/             # Worker & Supervisor Agents
│   ├── schema/             # Pydantic Models
│   └── tools/              # RAG & Web Search Tools
├── data/                   # Documents for RAG
├── design-deliverables.md  # Detailed Design Docs
└── semiconductor_ai_investment_flowchart_v3.svg
```

## 5. Getting Started
1. `.env` 파일에 API 키 설정 (`OPENAI_API_KEY`, `TAVILY_API_KEY`)
2. `pip install -r requirements.txt` (or use `uv`, `poetry`)
3. `python src/main.py` 실행

## 6. Loop & Corrective Strategy
- **Corrective RAG**: 검색 결과가 부실하거나 도메인 불일치 시 최대 3회 Loop 수행.
- **Adaptive Routing**: Decision 에이전트에서 '보류' 판정 시 Supervisor로 돌아가 분석 단계 재수행.

## Contributors 
- AI 1반: 김주환, 방다원, 지다은, 한상윤
