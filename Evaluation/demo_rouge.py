import asyncio
import importlib.util

# Load rouge.py directly — skips __init__.py and all its dependencies
spec = importlib.util.spec_from_file_location(
    "rouge", "Evaluation/metrics/rouge.py"
)
rouge_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rouge_module)
compute_rouge_score = rouge_module.compute_rouge_score

GROUND_TRUTH = "The sun is powered by nuclear fusion in its core."
ANSWER = "The sun produces energy by nuclear fusion happening in the core of the sun."

async def main():
    print("Ground truth:", GROUND_TRUTH)
    print("Answer:      ", ANSWER)
    print()
    for mode in ["precision", "recall", "fmeasure"]:
        score = await compute_rouge_score(ANSWER, GROUND_TRUTH, mode=mode)
        print(f"{mode:>10}: {score:.4f}")

asyncio.run(main())