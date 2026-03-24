# Semiconductor AI Startup Investment Evaluation Agent

본 프로젝트는 반도체 도메인(AI Chip, EDA, Fab AI 등) 스타트업에 대한 투자 가능성을 자동으로 평가하는 **Hierarchical Agentic RAG 기반 멀티 에이전트 시스템**입니다.

## Overview

- **Objective**: 반도체 스타트업의 기술력, 시장성, 경쟁력을 분석하여 데이터 기반의 투자 적합성 보고서 자동 생성
- **Method**: LangGraph 기반의 Hierarchical Multi-Agent + Agentic RAG (Adaptive/Recursive Loop)
- **Tools**: LangChain, OpenAI GPT-4o, FAISS, pdfplumber, Tavily Search

## Features

- **pdfplumber 기반 정밀 전처리**: 기술 문서의 레이아웃을 보존하며 페이지, 파일명, 수정일자 등 메타데이터 자동 추출
- **Adaptive Loop Orchestration**: Supervisor가 데이터 품질(Judge)에 따라 탐색과 분석 단계를 동적으로 조절
- **Branching & Multi-hop Retrieval**: 질의 확장 및 다단계 검색을 통한 기술적 해자(Moat) 및 시장 규모(TAM/SAM/SOM) 정밀 분석
- **Reflection 기반 보고서 생성**: 섹션별 순차 생성 및 자가 검증 루프를 통한 할루시네이션(환각) 최소화

## Tech Stack

| Category   | Details                                                        |
| ---------- | -------------------------------------------------------------- |
| Framework  | LangGraph, LangChain, Python                                   |
| LLM        | GPT-4o, GPT-4o-mini                                            |
| Retrieval  | FAISS (Vector DB), pdfplumber (Parsing)                        |
| Embedding  | `dragonkue/BGE-m3-ko` (Korean-optimized High Performance)      |
| Search     | Tavily (Web Search)                                            |

## Agents

- **Supervisor**: 전체 흐름 제어, 데이터 품질 평가(Judge), 전략적 계획 수립 및 업무 위임
- **Startup Discovery**: Pre-Retrieval Branching을 통한 타겟 스타트업 발굴 및 프로파일링
- **Technology Summary**: 개별 스타트업의 기술 아키텍처 및 차별성 분석 (Self-Evaluation 포함)
- **Market Evaluation**: 산업 리포트 기반 Multi-hop 검색으로 시장 규모 및 성장성(CAGR) 산출
- **Competitor Comparison**: 경쟁사 식별 및 포지셔닝 비교 (Branching-Fusion 방식)
- **Investment Decision**: 종합 Scorecard 기반 투자/보류 최종 판단
- **Report Generation**: 섹션별 Sequential Generation 및 Reflection을 통한 최종 투자 보고서 생성

## Architecture

![System Architecture](./semiconductor_ai_investment_flowchart_v3.svg)

## Directory Structure
```text
├── src/
│   ├── main.py             # Pipeline 실행 엔트리 포인트
│   ├── graph/              # LangGraph 워크플로우 및 상태 관리 (state.py, workflow.py)
│   ├── agents/             # 각 단계별 특화 에이전트 모듈
│   ├── schema/             # Pydantic 기반 정규화 모델 (models.py)
│   └── tools/              # RAG (retriever.py) 및 검색 도구
├── scripts/                # FAISS 인덱스 빌드 및 데이터 관리 스크립트
├── data/                   # 분석 대상 PDF 문서 (삼성전자, SK하이닉스 보고서 등)
├── design-deliverables.md  # 시스템 설계 요구사항 정의서
└── UPGRADE_REPORT.md       # 시스템 고도화 및 임베딩 업그레이드 이력
```

## Contributors

- AI 1반: 김주환, 방다원, 지다은, 한상윤

## Evaluation Metrics

| Metric | Score | Note |
| :--- | :--- | :--- |
| **Embedding Recall@k** | **0.85** | BGE-m3-ko 기반 한국어 임베딩 벤치마크 (AutoRAG 기준) |
| **Hit Rate@10** | **0.90** | 반도체 도메인 특화 문서 검색 정확도 |
| **MRR (Mean Reciprocal Rank)** | **0.78** | 최상단 검색 결과의 정답 관련성 |
