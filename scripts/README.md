# 스크립트

## FAISS 인덱스 빌드

`data/` 폴더의 모든 PDF를 오픈소스 임베딩 모델로 벡터화하여 FAISS에 저장합니다.

### 지원 모델

| 모델 | 설명 |
|------|------|
| **bge-m3** | BAAI/bge-m3, 다국어 |
| **kure-v1** | nlpai-lab/KURE-v1, 한국어 최적화 |
| **gte-qwen** | Alibaba-NLP/gte-Qwen2-1.5B-instruct, Qwen 계열 |

-> **dragonkue/BGE-m3-ko**로 업그레이드

### 사용법

```bash
uv run python scripts/build_faiss_index.py                    # bge-m3 (기본)
uv run python scripts/build_faiss_index.py --model kure-v1   # KURE-v1
uv run python scripts/build_faiss_index.py --model gte-qwen # Qwen
```

### 저장 경로

- FAISS 인덱스: `.cache/faiss_index_{model}/`
- HuggingFace 모델 캐시: `.cache/huggingface/` (워크스페이스 내, 권한 문제 방지)
