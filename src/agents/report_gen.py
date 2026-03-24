from typing import List, Dict
from langchain_openai import ChatOpenAI
from src.graph.state import GraphState
from pydantic import BaseModel, Field

class SectionGeneration(BaseModel):
    content: str = Field(description="Markdown content for this specific section")

class ReflectionResult(BaseModel):
    is_valid: bool = Field(description="Whether the content is factually correct and logically consistent")
    feedback: str = Field(description="Feedback if invalid")

class ReportAgent:
    def __init__(self, model_name="gpt-4o"):
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.section_llm = self.llm.with_structured_output(SectionGeneration)
        self.reflection_llm = self.llm.with_structured_output(ReflectionResult)

    def generate_section(self, section_name: str, context: str, previous_sections: str) -> str:
        prompt = f"""
        Generate the '{section_name}' section for a semiconductor investment report.
        Context: {context}
        Previous sections: {previous_sections}
        
        Write clear, professional markdown. Focus on data from the context.
        """
        
        for _ in range(3): # Max 3 tries per section
            result = self.section_llm.invoke(prompt)
            content = result.content
            
            # Reflection
            reflection_prompt = f"""
            Verify the following content for the '{section_name}' section.
            Content: {content}
            Retrieved Context: {context}
            
            Check for:
            1. Hallucinations (claims not in context)
            2. Logical consistency
            3. Professional tone
            """
            reflection = self.reflection_llm.invoke(reflection_prompt)
            
            if reflection.is_valid:
                print(f"Section '{section_name}' validated.")
                return content
            else:
                print(f"Section '{section_name}' failed reflection: {reflection.feedback}. Retrying...")
                prompt += f"\n\nRefinement feedback: {reflection.feedback}"
                
        return content # Fallback to last content if fails 3 times

    def __call__(self, state: GraphState):
        print("--- REPORT AGENT: SEQUENTIAL GENERATION WITH REFLECTION ---")
        
        # Collect all state data into a single context
        all_data = f"""
        Candidates: {state.get('startup_candidates', [])}
        Tech: {state.get('tech_summaries', [])}
        Market: {state.get('market_analyses', [])}
        Validation: {state.get('validation_results', [])}
        """
        
        sections = [
            "Executive Summary",
            "Startup Technology Analysis",
            "Market Opportunity",
            "Competitor Benchmarking",
            "Investment Verdict & Risks"
        ]
        
        final_report = "# Semiconductor AI Startup Investment Report\n\n"
        
        for section in sections:
            print(f"Generating section: {section}...")
            section_content = self.generate_section(section, all_data, final_report)
            final_report += f"## {section}\n\n{section_content}\n\n"
            
        return {"final_report": final_report, "is_done": True}
