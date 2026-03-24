import asyncio
from dotenv import load_dotenv
from src.graph.workflow import create_workflow

load_dotenv()

async def main():
    # 1. Create the workflow graph
    app = create_workflow()
    
    # 2. Define initial state
    initial_state = {
        "question": "What are the investment opportunities in high-bandwidth memory (HBM) and AI accelerators as mentioned in recent reports?",
        "target_domain": "Semiconductor AI",
        "startup_candidates": [],
        "validation_results": [],
        "tech_summaries": [],
        "market_analyses": [],
        "judge_history": [],
        "iteration_count": 0,
        "is_done": False
    }
    
    # 3. Run the graph with streaming
    print("\n" + "="*50)
    print("🚀 STARTING HIERARCHICAL AGENTIC RAG PIPELINE")
    print("="*50)
    
    final_state = initial_state
    async for event in app.astream(initial_state, stream_mode="values"):
        final_state = event # Keep track of the latest state
        # (Optional: Add more granular logging here)

    # 4. Final Output Display
    print("\n" + "🏁 PIPELINE COMPLETE")
    print("="*50)
    print("\n[FINAL INVESTMENT REPORT]")
    print(final_state.get("final_report", "No report generated."))
    
    if final_state.get("validation_results"):
        print("\n[DETAILED SCORING]")
        for res in final_state["validation_results"]:
            status = "✅ PASS" if res.passed else "❌ HOLD"
            print(f"- {res.startup_name}: {res.score} pts [{status}]")
            print(f"  Reason: {res.reason}")

if __name__ == "__main__":
    asyncio.run(main())
