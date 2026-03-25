from typing import List, Annotated, TypedDict, Optional, Dict
import operator
from src.schema.models import (
    StartupProfile,
    ValidationResult,
    TechSummary,
    MarketAnalysis,
    JudgeVerdict,
    CompetitorProfile,
    HITLRecord,
)


class GraphState(TypedDict):
    # ── [Input & Flow Control] ──
    question: str
    target_domain: str

    route_type: str                         # "direct" | "pipeline"
    direct_answer: Optional[str]
    detected_domain: str
    next_agent: str                         # Next node to execute
    agent_queries: Dict[str, str]          # {agent_name: rewritten_query} — Supervisor sets before parallel run

    # ── [Worker Results (Accumulated)] ──
    startup_candidates: List[StartupProfile]                            # overwrite (discovery sets current candidate)
    candidate_pool: List[StartupProfile]                                # full pool from discovery (overwrite)
    pool_offset: int                                                     # next candidate index (overwrite)
    validation_results: Annotated[List[ValidationResult], operator.add]
    tech_summaries: Annotated[List[TechSummary], operator.add]
    market_analyses: Annotated[List[MarketAnalysis], operator.add]
    competitor_profiles: Annotated[List[CompetitorProfile], operator.add]

    # ── [Judge & Loop Control] ──
    judge_history: Annotated[List[JudgeVerdict], operator.add]
    mini_judge_history: Annotated[List[JudgeVerdict], operator.add]
    judge_iteration: int                    # overwrite (Judge node only)
    judge_passed: bool
    judge_retry_target: List[str]
    retry_agents: List[str]           # supervisor → mini_supervisor_router 중계 필드

    iteration_count: int
    is_done: bool

    # ── [HITL] ──
    hitl_enabled: bool
    hitl_records: Annotated[List[HITLRecord], operator.add]

    # ── [Decision] ──
    investment_decision: Optional[str]      # "invest" | "hold" | "additional_review"

    # ── [Final Output] ──
    selected_startup: Optional[str]
    final_report: Optional[str]
    report_pdf_path: Optional[str]

    # ── [Logging] ──
    logs: Annotated[List[str], operator.add]
