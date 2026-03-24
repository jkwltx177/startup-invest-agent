# 에이전트 아키텍처 및 RAG 파이프라인 업그레이드 보고서

본 보고서는 `agents_detail.md` 및 `preprocessing_embedding.md`의 요구사항을 반영하여 수행된 시스템 고도화 내용을 정리합니다.

## 1. RAG 전처리 및 임베딩 업그레이드

### 변경 사항 (이전 vs 현재)
| 항목 | 이전 상태 | 현재 업그레이드 상태 |
| :--- | :--- | :--- |
| **PDF 로더** | `PyPDFLoader` (단순 텍스트) | `pdfplumber` 기반 `CustomPDFLoader` (레이아웃 보존) |
| **메타데이터** | 출처(source)만 포함 | 파일명, 페이지 번호, 수정 일자(MOD) 필수 태깅 |
| **임베딩 모델** | `BAAI/bge-m3` (다국어 범용) | `dragonkue/BGE-m3-ko` (한국어 특화 고성능 모델) |
| **청크 전략** | 1000/100 (고정 크기) | 800/150 (넉넉한 오버랩, 맥락 유지 강화) |

### 주요 개선점
- **정밀한 텍스트 추출**: `pdfplumber`를 사용하여 표나 복잡한 문서 구조에서도 읽기 순서를 최대한 유지하며 텍스트를 추출합니다.
- **근거 강화**: 검색된 각 청크에 페이지 번호와 수정 일자를 포함하여, 생성된 보고서의 신뢰성을 높였습니다.

## 2. 에이전트 구조 및 루프 고도화

### 에이전트별 업그레이드 내용
1.  **Supervisor (Adaptive Loop)**
    - 단순 순차 제어에서 **Judge 기반 적응형 루프**로 변경되었습니다.
    - 수집된 데이터의 품질(Coverage, Consistency)을 점수화하여 다음 단계를 결정합니다.
2.  **Discovery Agent (Branching)**
    - 사용자 질의를 3-4개의 세부 질의로 확장(Query Expansion)하여 병렬 검색을 수행하는 **Pre-Retrieval Branching**을 구현했습니다.
3.  **Tech Summary & Market Eval (Corrective/Multi-hop)**
    - 검색 결과가 부족할 경우 스스로 피드백을 주거나, 연관 정보를 단계적으로 찾아가는 **Multi-hop Retrieval** 로직을 강화했습니다.
4.  **Competitor Agent (Branching-Fusion)**
    - 각 경쟁사를 개별 분석한 뒤 하나로 합치는 구조로 정교화되었습니다.
5.  **Report Agent (Sequential Generation & Reflection)**
    - 전체 보고서를 한 번에 쓰지 않고 섹션별로 순차 생성합니다.
    - 각 섹션 생성 후 **Reflection Loop**를 통해 할루시네이션(환각) 여부를 자가 검증합니다.

## 3. 실행 및 검증 결과
- `scripts/build_faiss_index.py`를 통해 신규 임베딩 모델 기반 인덱스 재구축 완료.
- `uv run python -m src.main` 실행을 통해 전체 파이프라인의 정상 동작 및 루프 제어 확인.

---
**업데이트 날짜:** 2026-03-24
