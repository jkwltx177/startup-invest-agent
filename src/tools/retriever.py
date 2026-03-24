import os
import time
from pathlib import Path
from typing import List, Optional
import pdfplumber
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

class CustomPDFLoader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def load(self) -> List[Document]:
        documents = []
        mod_date = time.ctime(os.path.getmtime(self.file_path))
        
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                # 텍스트 추출 (pdfplumber의 extract_text는 기본적으로 레이아웃을 어느 정도 유지함)
                page_text = page.extract_text() or ""
                
                metadata = {
                    "source": self.file_path.name,
                    "page": page.page_number,
                    "mod_date": mod_date,
                }
                documents.append(Document(page_content=page_text, metadata=metadata))
        return documents

class SemiconductorRetriever:
    def __init__(
        self,
        index_path: str = ".cache/faiss_index_bge-m3-ko",
        data_dir: str = "data",
        model_name: str = "dragonkue/BGE-m3-ko",
    ):
        self.index_path = Path(index_path)
        self.data_dir = Path(data_dir)
        # 한국어 최적화 모델 또는 BGE-M3 (design-deliverables.md 및 preprocessing_embedding.md 기준)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={'device': 'cpu'}, 
            encode_kwargs={'normalize_embeddings': True}
        )
        self.vectorstore = None

    def create_index(self):
        """PDF 데이터를 읽어 벡터 DB 생성 및 로컬 저장"""
        if not self.data_dir.exists():
            print(f"Warning: {self.data_dir} directory not found.")
            return

        documents = []
        pdf_files = sorted(list(self.data_dir.glob("*.pdf")))
        
        if not pdf_files:
            print("No PDF files found in data directory.")
            return

        for pdf_path in pdf_files:
            try:
                loader = CustomPDFLoader(str(pdf_path))
                documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {pdf_path}: {e}")

        if not documents:
            return

        # Chunking: RecursiveCharacterTextSplitter 사용 (넉넉한 Overlap)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800, 
            chunk_overlap=150,
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
            print(f"Index not found at {self.index_path}. Creating a new one...")
            self.create_index()

    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        """유사도 기반 검색 수행"""
        if not self.vectorstore:
            self.load_index()
        
        if not self.vectorstore:
            return []
            
        return self.vectorstore.similarity_search(query, k=k)

    def get_context(self, query: str, k: int = 5) -> str:
        """검색된 문서들을 하나의 문자열 컨텍스트로 결합 (메타데이터 포함)"""
        docs = self.retrieve(query, k=k)
        context_parts = []
        for d in docs:
            src = d.metadata.get('source', 'Unknown')
            pg = d.metadata.get('page', '?')
            mod = d.metadata.get('mod_date', 'Unknown')
            context_parts.append(f"[Source: {src}, Page: {pg}, MOD: {mod}]\n{d.page_content}")
        
        return "\n\n---\n\n".join(context_parts)
