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
