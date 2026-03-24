import asyncio
from dotenv import load_dotenv
from src.graph.workflow import create_workflow

load_dotenv()

async def main():
    # 1. Create the workflow graph
    app = create_workflow()
    
    # 2. Define initial state
    initial_state = {
        "question": "Identify and evaluate promising AI chip startups specializing in edge computing.",
        "target_domain": "Semiconductor AI",
        "startup_candidates": [],
        "validation_results": [],
        "tech_summaries": [],
        "market_analyses": [],
        "judge_history": [],
        "iteration_count": 0,
        "is_done": False
    }
    
    # 3. Run the graph
    print("Starting Hierarchical Agentic RAG Pipeline...")
    async for event in app.astream(initial_state):
        for node_name, output in event.items():
            print(f"\n[Node: {node_name}]")
            # print(output)
            
    # 4. Final Result
    final_state = await app.ainvoke(initial_state)
    print("\n" + "="*50)
    print("FINAL REPORT GENERATED:")
    print(final_state.get("final_report"))

if __name__ == "__main__":
    asyncio.run(main())
