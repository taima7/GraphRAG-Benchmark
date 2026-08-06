"""ROUGE-L demonstration for doc/metrics_explained.md.

Mirrors the structure of Evaluation/generation_eval.py -- same prediction-file
format, same field names, same compute_rouge_score() -- reduced to a single
metric so the numbers can be checked by hand. The example data lives in
doc/examples/rouge_example.json, not in this file.

Needs only rouge_score installed; see _load_compute_rouge_score() below.

    python doc/demo_rouge.py
    python doc/demo_rouge.py --data_file doc/examples/rouge_example.json
"""
import asyncio
import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = Path(__file__).resolve().parent / "examples" / "rouge_example.json"
MODES = ["precision", "recall", "fmeasure"]


def _load_compute_rouge_score() -> Callable:
    """Load Evaluation/metrics/rouge.py as a standalone module.

    generation_eval.py does 'from Evaluation.metrics import compute_rouge_score',
    which executes Evaluation/metrics/__init__.py and therefore imports every
    other metric, pulling in langchain_core, json5 and json_repair. ROUGE-L needs
    none of those, so this demo loads the single module it uses and stays
    runnable with only rouge_score installed.
    """
    spec = importlib.util.spec_from_file_location(
        "rouge", REPO_ROOT / "Evaluation" / "metrics" / "rouge.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compute_rouge_score


compute_rouge_score = _load_compute_rouge_score()


async def evaluate_sample(answer: str, ground_truth: str) -> Dict[str, float]:
    """Evaluate the ROUGE-L scores for a single sample."""
    tasks = {mode: compute_rouge_score(answer, ground_truth, mode=mode) for mode in MODES}
    task_results = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), task_results))


async def evaluate_dataset(file_data: List[Dict[str, Any]]) -> None:
    """Evaluate every sample of a prediction file and print the scores."""
    for item in file_data:
        ground_truth = item["ground_truth"]
        answer = item["generated_answer"]

        print(f"Question:     {item['question']}")
        print(f"Ground truth: {ground_truth}")
        print(f"Answer:       {answer}")

        scores = await evaluate_sample(answer, ground_truth)
        for mode, score in scores.items():
            print(f"{mode:>13}: {score:.4f}")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="ROUGE-L demonstration")
    parser.add_argument(
        "--data_file",
        default=DEFAULT_DATA_FILE,
        help="Prediction file in the format Evaluation/generation_eval.py consumes"
    )
    args = parser.parse_args()

    print(f"Loading evaluation data from {args.data_file}...")
    with open(args.data_file, 'r') as f:
        file_data = json.load(f)  # A list of question items

    await evaluate_dataset(file_data)


if __name__ == "__main__":
    asyncio.run(main())
