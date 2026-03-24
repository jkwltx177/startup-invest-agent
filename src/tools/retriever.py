import os
from pathlib import Path
from typing import List
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

class SemiconductorRetriever:
    def __init__(self, index_path: str = ".cache/faiss_index", data_dir: str = "data"):
        self.index_path = Path(index_path)
        self.data_dir = Path(data_dir)
        # BAAI/bge-m3 model 선정 (design-deliverables.md 기준)
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': 'cpu'}, # GPU 사용 시 'cuda'
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vectorstore = None

    def create_index(self):
        """PDF 데이터를 읽어 벡터 DB 생성 및 로컬 저장"""
        if not self.data_dir.exists():
            print(f"Warning: {self.data_dir} directory not found.")
            return

        documents = []
        pdf_files = list(self.data_dir.glob("*.pdf"))
        
        if not pdf_files:
            print("No PDF files found in data directory.")
            return

        for pdf_path in pdf_files:
            try:
                loader = PyPDFLoader(str(pdf_path))
                documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {pdf_path}: {e}")

        if not documents:
            return

        # 설계 제약: 문서당 50페이지 이하, 총 200페이지 이내 반영된 Chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=100,
            add_start_index=True
        )
        splits = text_splitter.split_documents(documents)

        # FAISS 인덱스 생성 및 저장
        self.vectorstore = FAISS.from_documents(splits, self.embeddings)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.vectorstore.save_local(str(self.index_path))
        print(f"Successfully indexed {len(pdf_files)} files into {self.index_path}")

    def load_index(self):
        """저장된 인덱스 로드"""
        if (self.index_path / "index.faiss").exists():
            self.vectorstore = FAISS.load_local(
                str(self.index_path), 
                self.embeddings, 
                allow_dangerous_deserialization=True
            )
        else:
            print("Index not found. Creating a new one...")
            self.create_index()

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """유사도 기반 검색 수행"""
        if not self.vectorstore:
            self.load_index()
        
        if not self.vectorstore:
            return []
            
        return self.vectorstore.similarity_search(query, k=k)

    def get_context(self, query: str, k: int = 5) -> str:
        """검색된 문서들을 하나의 문자열 컨텍스트로 결합"""
        docs = self.retrieve(query, k=k)
        return "\n\n".join([f"[Source: {d.metadata.get('source', 'Unknown')}] {d.page_content}" for d in docs])
