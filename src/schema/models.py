from typing import List, Optional
from pydantic import BaseModel, Field

class StartupProfile(BaseModel):
    name: str = Field(description="Name of the startup")
    domain: str = Field(description="Sub-domain in semiconductor (e.g., AI chip, EDA, Fab AI)")
    investment_stage: str = Field(description="Current investment stage (e.g., Series A, Seed)")
    description: str = Field(description="Short description of the company")
    relevance_score: float = Field(description="Score (0-1) indicating relevance to the semiconductor domain")

class TechSummary(BaseModel):
    startup_name: str
    tech_type: str = Field(description="Category of the core technology")
    core_mechanism: str = Field(description="Key technical mechanism or algorithm")
    application_area: str = Field(description="Primary application area in semiconductor")
    differentiation: str = Field(description="Technical innovation/improvement over existing solutions")
    strengths: List[str]
    weaknesses: List[str]

class MarketAnalysis(BaseModel):
    startup_name: str
    market_size: str = Field(description="TAM/SAM/SOM estimates")
    growth_rate: str = Field(description="CAGR estimate")
    market_position: str = Field(description="Estimated market position (e.g., Niche, Challenger)")
    investment_attractiveness: str = Field(description="Score or qualitative assessment")

class ValidationResult(BaseModel):
    startup_name: str
    passed: bool
    score: float
    reason: str

class JudgeVerdict(BaseModel):
    iteration: int
    feedback: str
    next_action: str
