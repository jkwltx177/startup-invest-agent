from typing import List, Annotated, TypedDict, Optional, Union
import operator
from src.schema.models import (
    StartupProfile, 
    ValidationResult, 
    TechSummary, 
    MarketAnalysis, 
    JudgeVerdict
)

class GraphState(TypedDict):
    # ── [Input & Flow Control] ──
    question: Annotated[str, "Original user query"]
    target_domain: Annotated[str, "Target industry domain (e.g., semiconductor AI)"]
    
    next_agent: Annotated[str, "Next node to execute"]
    active_agents: Annotated[List[str], "Currently active worker agents"]
    candidate_eval_index: Annotated[int, "현재 순차 평가 중인 후보 인덱스 (0~4)"]
    evaluation_target_name: Annotated[Optional[str], "현재 평가 대상 스타트업명 (단일)"]
    last_decision_passed: Annotated[bool, "직전 decision에서 투자 승인 여부"]
    
    # ── [Worker Results (Accumulated)] ──
    startup_candidates: Annotated[List[StartupProfile], operator.add]
    validation_results: Annotated[List[ValidationResult], operator.add]
    tech_summaries: Annotated[List[TechSummary], operator.add]
    market_analyses: Annotated[List[MarketAnalysis], operator.add]
    
    # ── [Judge & Loop Control] ──
    judge_history: Annotated[List[JudgeVerdict], operator.add]
    iteration_count: Annotated[int, "Current loop iteration count"]
    is_done: Annotated[bool, "Pipeline completion flag"]
    
    # ── [Final Output] ──
    selected_startup: Annotated[Optional[str], "Final selected startup name"]
    final_report: Annotated[Optional[str], "Generated markdown investment report"]
    report_file_path: Annotated[Optional[str], "Path to saved report file (PDF)"]
    report_regeneration_count: Annotated[int, "Number of report regenerate attempts"]
    all_hold: Annotated[bool, "True when all candidates are on hold (no investment)"]
