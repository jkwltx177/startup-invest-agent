from typing import Dict, List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class StartupProfile(BaseModel):
    name: str = Field(description="Name of the startup")
    domain: str = Field(description="Sub-domain in semiconductor (e.g., AI chip, EDA, Fab AI)")
    investment_stage: str = Field(description="Current investment stage (e.g., Series A, Seed)")
    description: str = Field(description="Short description of the company")
    relevance_score: float = Field(description="Score (0-1) indicating relevance to the semiconductor domain")
    source_urls: List[str] = Field(default_factory=list, description="Source URLs for this startup's information")


class TechSummary(BaseModel):
    startup_name: str
    tech_type: str = Field(description="Category of the core technology")
    core_mechanism: str = Field(description="Key technical mechanism or algorithm")
    application_area: str = Field(description="Primary application area in semiconductor")
    differentiation: str = Field(description="Technical innovation/improvement over existing solutions")
    strengths: List[str]
    weaknesses: List[str]
    sources: List[str] = Field(default_factory=list, description="Source URLs or document IDs")
    confidence_score: float = Field(default=0.0, description="Confidence score for this analysis (0-1)")


class MarketAnalysis(BaseModel):
    startup_name: str
    market_size: str = Field(description="TAM/SAM/SOM estimates")
    growth_rate: str = Field(description="CAGR estimate")
    market_position: str = Field(description="Estimated market position (e.g., Niche, Challenger)")
    investment_attractiveness: str = Field(description="Score or qualitative assessment")
    sources: List[str] = Field(default_factory=list, description="Source URLs or document IDs")
    confidence_score: float = Field(default=0.0, description="Confidence score for this analysis (0-1)")


class CompetitorProfile(BaseModel):
    startup_name: str = Field(description="The startup being analyzed")
    competitor_name: str = Field(description="Name of the competing company")
    tech_gap_summary: str = Field(description="Summary of technology gap between startup and competitor")
    market_share_pct: float = Field(default=0.0, description="Estimated market share percentage of competitor")
    funding_total_usd: float = Field(default=0.0, description="Total funding of competitor in USD")
    strategic_partners: List[str] = Field(default_factory=list, description="Key strategic partners of competitor")
    source_urls: List[str] = Field(default_factory=list, description="Source URLs for competitor information")
    vector_doc_ids: List[str] = Field(default_factory=list, description="Vector DB document IDs used")


class ValidationResult(BaseModel):
    startup_name: str
    passed: bool
    score: float
    reason: str
    investment_category: Literal["invest", "hold", "additional_review"] = Field(
        default="hold", description="Investment category decision"
    )
    scorecard_breakdown: Dict[str, int] = Field(
        default_factory=dict, description="Breakdown of scores by category"
    )
    investment_risk: str = Field(default="", description="Summary of key investment risks")


class JudgeVerdict(BaseModel):
    iteration: int
    feedback: str
    passed: bool = Field(default=False, description="Whether the judgment passed all criteria")
    failed_criteria: List[str] = Field(default_factory=list, description="List of failed criteria")
    retry_strategy: Literal["re_plan", "re_route", "re_retrieve", "re_generate"] = Field(
        default="re_generate", description="Strategy for retrying failed agents"
    )
    target_agents: List[str] = Field(default_factory=list, description="Agents to target for retry")


class HITLRequest(BaseModel):
    checkpoint_id: str = Field(description="Checkpoint ID (CP-1 through CP-5)")
    message: str = Field(description="Message to display to the user")
    data: dict = Field(default_factory=dict, description="Relevant data for the user to review")
    options: List[str] = Field(default_factory=list, description="Available options for the user")
    is_blocking: bool = Field(default=True, description="Whether this checkpoint blocks execution")


class HITLRecord(BaseModel):
    checkpoint_id: str
    question: str
    user_response: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
