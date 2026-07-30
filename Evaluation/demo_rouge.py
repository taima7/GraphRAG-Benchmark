import asyncio
from Evaluation.metrics.rouge import compute_rouge_score

# Change these two lines to your own example
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