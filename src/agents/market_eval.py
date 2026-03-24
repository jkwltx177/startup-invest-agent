from typing import List
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from src.schema.models import MarketAnalysis
from src.tools.retriever import SemiconductorRetriever
from pydantic import BaseModel, Field


class MarketAnalysisList(BaseModel):
    analyses: List[MarketAnalysis] = Field(description="List of market analyses for each candidate")


class MarketQualityCheck(BaseModel):
    is_sufficient: bool = Field(description="Whether the market data is detailed and sourced")
    missing_elements: List[str] = Field(description="Missing market data points (TAM, SAM, SOM, CAGR)")


class MarketEvalAgent:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.structured_llm = self.llm.with_structured_output(MarketAnalysisList)
        self.quality_llm = self.llm.with_structured_output(MarketQualityCheck)
        self.retriever = SemiconductorRetriever()

    def __call__(self, state: GraphState):
        print("\n>>> [market_eval] 시장 분석 실행 중...", flush=True)
        candidates = state.get("startup_candidates", [])
        target = (state.get("evaluation_target_name") or "").strip()
        if target:
            candidates = [c for c in candidates if (c.name or "").strip() == target]
        if not candidates:
            return {"market_analyses": []}

        all_analyses = []
        for startup in candidates:
            print(f"Analyzing market for {startup.name}...", flush=True)

            broad_context = self.retriever.get_context(
                f"Market size, TAM, SAM, SOM and CAGR for {startup.domain} semiconductor segment", k=5
            )
            focused_context = self.retriever.get_context(
                f"{startup.name} market share, potential customers, and target segment in {startup.domain}", k=5
            )

            combined_context = f"BROAD MARKET CONTEXT:\n{broad_context}\n\nFOCUSED CONTEXT:\n{focused_context}"

            prompt = f"""
            Analyze the market potential of {startup.name} using the provided context.
            Extract TAM/SAM/SOM and growth rate (CAGR) if available.
            Context: {combined_context}
            """

            try:
                result = self.structured_llm.invoke(prompt)
                analysis = result.analyses[0] if result and result.analyses else None

                if analysis:
                    analysis.startup_name = startup.name
                    q_prompt = f"Verify if this market analysis of {startup.name} is sufficient based on context: {analysis.model_dump_json()}\nContext: {combined_context}"
                    quality = self.quality_llm.invoke(q_prompt)

                    if not quality.is_sufficient:
                        print(f"Warning: Market data for {startup.name} is lacking: {quality.missing_elements}")

                    all_analyses.append(analysis)
            except Exception as e:
                print(f"Error in Market Eval for {startup.name}: {e}")

        return {"market_analyses": all_analyses}
