#!/usr/bin/env python3
"""
data/ 폴더의 모든 PDF를 오픈소스 임베딩 모델로 벡터화하여 FAISS에 저장하는 스크립트.

캐시를 프로젝트 .cache/huggingface 에 저장하여 sandbox/권한 문제 방지.

사용 예:
    uv run python scripts/build_faiss_index.py                    # 기본: bge-m3
    uv run python scripts/build_faiss_index.py --model kure-v1     # KURE-v1 (한국어)
    uv run python scripts/build_faiss_index.py --model gte-qwen   # Qwen 계열
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트 기준 HuggingFace 캐시를 워크스페이스 안으로 설정 (권한 문제 방지)
_project_root = Path(__file__).resolve().parent.parent
_hf_cache = _project_root / ".cache" / "huggingface"
_hf_cache.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(_hf_cache)
os.environ["HF_HUB_CACHE"] = str(_hf_cache / "hub")
os.environ["TRANSFORMERS_CACHE"] = str(_hf_cache)

sys.path.insert(0, str(_project_root))

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.tools.retriever import CustomPDFLoader


EMBEDDING_MODELS = {
    "bge-m3": {
        "model_name": "BAAI/bge-m3",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    },
    "kure-v1": {
        "model_name": "nlpai-lab/KURE-v1",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    },
    "bge-m3-ko": {
        "model_name": "dragonkue/BGE-m3-ko",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    },
    "gte-qwen": {
        "model_name": "Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    },
}


def build_index(
    data_dir: Path = None,
    output_dir: Path = None,
    model_preset: str = "kure-v1",
    chunk_size: int = 800,
    chunk_overlap: int = 150,
):
    data_dir = data_dir or _project_root / "data"
    cfg = EMBEDDING_MODELS.get(model_preset)
    if not cfg:
        print(f"[ERROR] 지원 모델: {list(EMBEDDING_MODELS.keys())}")
        return False

    output_dir = output_dir or _project_root / ".cache" / f"faiss_index_{model_preset}"

    if not data_dir.exists():
        print(f"[ERROR] data 폴더가 없습니다: {data_dir}")
        return False

    pdf_files = sorted(data_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] PDF 파일이 없습니다: {data_dir}")
        return False

    print(f"[1/4] 임베딩 모델 로드: {cfg['model_name']} (캐시: {_hf_cache})")
    embeddings = HuggingFaceEmbeddings(
        model_name=cfg["model_name"],
        model_kwargs=cfg["model_kwargs"],
        encode_kwargs=cfg["encode_kwargs"],
    )

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )

    print(f"[2/4] PDF 파일별 처리 (CustomPDFLoader 사용, 총 {len(pdf_files)}개)")
    vectorstore = None
    total_chunks = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        try:
            loader = CustomPDFLoader(str(pdf_path))
            docs = loader.load()
            splits = text_splitter.split_documents(docs)
            print(f"  [{i}/{len(pdf_files)}] {pdf_path.name}: {len(docs)}페이지 → {len(splits)}청크")

            if vectorstore is None:
                vectorstore = FAISS.from_documents(splits, embeddings)
            else:
                vectorstore.add_documents(splits)
            total_chunks += len(splits)
        except Exception as e:
            print(f"  [{i}/{len(pdf_files)}] [경고] {pdf_path.name} 실패: {e}")

    if vectorstore is None or total_chunks == 0:
        print("[ERROR] 처리된 문서가 없습니다.")
        return False

    print(f"[3/4] 총 {total_chunks}개 청크 생성")
    print(f"[4/4] FAISS 인덱스 저장: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(output_dir))
    print(f"[완료] {len(pdf_files)}개 PDF → {total_chunks}개 청크 → {output_dir}")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="data/ PDF를 임베딩하여 FAISS에 저장")
    parser.add_argument(
        "--model", "-m",
        choices=["bge-m3", "kure-v1", "bge-m3-ko", "gte-qwen"],
        default="kure-v1",
        help="임베딩 모델",
    )
    parser.add_argument("--data-dir", "-d", type=Path, default=None)
    parser.add_argument("--output", "-o", type=Path, default=None)
    parser.add_argument("--chunk-size", type=int, default=800, help="청크 크기 (작을수록 청크 많음)")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="청크 중첩")
    args = parser.parse_args()

    ok = build_index(
        data_dir=args.data_dir,
        output_dir=args.output,
        model_preset=args.model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
