from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import StartupProfile
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field

# 여러 스타트업을 한 번에 받기 위한 래퍼 클래스
class StartupList(BaseModel):
    candidates: List[StartupProfile] = Field(description="List of identified semiconductor startups")

class DiscoveryAgent:
    def __init__(self, model_name="gpt-4o"):
        # Structured Output을 위해 llm 설정
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(StartupList)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("--- DISCOVERY AGENT: EXTRACTING FROM REAL PDF ---")
        question = state["question"]
        
        # 1. RAG 검색 (data/ 폴더의 삼성, SK, 산업 리포트 등 활용)
        context = self.retriever.get_context(f"Semiconductor companies and startups mentioned in: {question}", k=10)
        
        # 2. LLM이 컨텍스트에서 실제 기업 정보 추출
        prompt = f"""
        You are a semiconductor investment analyst. Based on the provided context, 
        identify and profile the companies or startups that match the user's interest.
        
        Context:
        {context}
        
        User Query:
        {question}
        
        If specific startups aren't found, look for company names mentioned in the industry trend reports.
        Assign a relevance_score (0-1) based on how well they match the 'semiconductor' domain.
        """
        
        try:
            result = self.structured_llm.invoke(prompt)
            candidates = result.candidates if result else []
            
            # 검색 결과가 전혀 없을 경우에 대한 예외 처리
            if not candidates:
                print("No candidates found in PDF. Using industry trend keywords.")
                # (생략: 필요시 기본값이나 재검색 로직)
        except Exception as e:
            print(f"Error in Structured Output: {e}")
            candidates = []
        
        return {"startup_candidates": candidates}
