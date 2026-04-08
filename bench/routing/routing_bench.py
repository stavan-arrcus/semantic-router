"""
Routing Accuracy Benchmark

Sends MMLU-style questions through the semantic router and measures whether
the domain classifier routes each question to the correct backend.

Usage:
    cd bench
    python3 -m routing.routing_bench \
        --endpoint http://127.0.0.1:8801/v1 \
        --qwen-model "qwen2.5:3b" \
        --llama-model "tinyllama"
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Routing accuracy benchmark for semantic router domain classifier"
    )
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8801/v1",
        help="Envoy endpoint URL (default: http://127.0.0.1:8801/v1)",
    )
    parser.add_argument(
        "--api-key",
        default="1234",
        help="API key for the endpoint (default: 1234)",
    )
    parser.add_argument(
        "--qwen-model",
        default="qwen2.5:3b",
        help="Model name served by the qwen backend (default: qwen2.5:3b)",
    )
    parser.add_argument(
        "--llama-model",
        default="tinyllama",
        help="Model name served by the llama backend (default: tinyllama)",
    )
    parser.add_argument(
        "--data",
        default=os.path.join(
            os.path.dirname(__file__), "..", "data", "routing_bench_data.json"
        ),
        help="Path to routing benchmark data JSON",
    )
    parser.add_argument(
        "--samples-per-domain",
        type=int,
        default=None,
        help="Limit questions per domain (default: use all)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write routing_results.json (default: no file output)",
    )
    return parser.parse_args()


def load_questions(
    data_path: str,
    samples_per_domain: Optional[int],
) -> List[Dict[str, Any]]:
    """Load questions from JSON, optionally capping per domain."""
    with open(data_path) as f:
        questions = json.load(f)

    if samples_per_domain is None:
        return questions

    by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for q in questions:
        by_domain.setdefault(q["domain"], []).append(q)

    result: List[Dict[str, Any]] = []
    for domain_questions in by_domain.values():
        result.extend(domain_questions[:samples_per_domain])
    return result


def detect_backend(model_name: str, qwen_model: str, llama_model: str) -> str:
    """Map a response model name to a backend label."""
    if model_name == qwen_model:
        return "qwen"
    if model_name == llama_model:
        return "llama"
    return "unknown"


def format_question(question: Dict[str, Any]) -> str:
    """Format a question record into a prompt string."""
    letters = ["A", "B", "C", "D", "E", "F"]
    options_text = "\n".join(
        f"{letters[i]}) {opt}" for i, opt in enumerate(question["options"])
    )
    return f"{question['question']}\n\nOptions:\n{options_text}"


def run_benchmark(
    questions: List[Dict[str, Any]],
    endpoint: str,
    api_key: str,
    qwen_model: str,
    llama_model: str,
) -> Dict[str, Any]:
    """Send all questions to the router and collect routing results."""
    from openai import OpenAI

    client = OpenAI(base_url=endpoint, api_key=api_key)
    results = []
    misses = []

    for q in questions:
        prompt = format_question(q)
        t0 = time.time()
        try:
            response = client.chat.completions.create(
                model="auto",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
            )
            got_model = response.model
        except Exception as exc:
            got_model = f"error:{exc}"
        latency_ms = (time.time() - t0) * 1000

        got_backend = detect_backend(got_model, qwen_model, llama_model)
        correct = got_backend == q["expected_backend"]

        result = {
            "id": q["id"],
            "domain": q["domain"],
            "expected": q["expected_backend"],
            "got": got_backend,
            "got_model": got_model,
            "correct": correct,
            "latency_ms": latency_ms,
            "question": q["question"],
        }
        results.append(result)

        if not correct:
            misses.append(result)
            print(f"MISS [{q['id']}] expected={q['expected_backend']} got={got_backend}")
            print(f"  \"{q['question']}\"")

    return {"results": results, "misses": misses}


def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute per-domain and overall accuracy from results."""
    by_domain: Dict[str, Dict[str, Any]] = {}
    for r in results:
        d = r["domain"]
        if d not in by_domain:
            by_domain[d] = {"correct": 0, "total": 0, "expected": r["expected"]}
        by_domain[d]["total"] += 1
        if r["correct"]:
            by_domain[d]["correct"] += 1

    for d, stats in by_domain.items():
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
        domain_results = [r for r in results if r["domain"] == d]
        stats["avg_latency_ms"] = sum(r["latency_ms"] for r in domain_results) / len(domain_results)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    avg_latency_ms = sum(r["latency_ms"] for r in results) / total if total > 0 else 0.0
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0.0,
        "avg_latency_ms": avg_latency_ms,
        "by_domain": by_domain,
    }


def print_table(summary: Dict[str, Any]) -> None:
    """Print the routing accuracy table to stdout."""
    sep = "─" * 72
    print(f"\n{'Domain':<20} {'Expected':<10} {'Correct':<9} {'Total':<7} {'Accuracy':<12} Avg Latency")
    print(sep)
    for domain, stats in sorted(summary["by_domain"].items()):
        print(
            f"{domain:<20} {stats['expected']:<10} {stats['correct']:<9}"
            f" {stats['total']:<7} {stats['accuracy'] * 100:.1f}%{'':9} {stats['avg_latency_ms']:.0f}ms"
        )
    print(sep)
    print(
        f"{'OVERALL':<20} {'':<10} {summary['correct']:<9}"
        f" {summary['total']:<7} {summary['accuracy'] * 100:.1f}%{'':9} {summary['avg_latency_ms']:.0f}ms"
    )
    print()


def main() -> None:
    args = parse_args()

    data_path = os.path.abspath(args.data)
    if not os.path.exists(data_path):
        print(f"Error: data file not found: {data_path}", file=sys.stderr)
        sys.exit(1)

    questions = load_questions(data_path, args.samples_per_domain)
    print(f"Loaded {len(questions)} questions from {data_path}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Backends: qwen={args.qwen_model!r}  llama={args.llama_model!r}\n")

    bench = run_benchmark(
        questions, args.endpoint, args.api_key, args.qwen_model, args.llama_model
    )
    summary = compute_summary(bench["results"])
    print_table(summary)

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        output_path = os.path.join(args.output_dir, "routing_results.json")
        with open(output_path, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total": summary["total"],
                        "correct": summary["correct"],
                        "accuracy": summary["accuracy"],
                        "avg_latency_ms": summary["avg_latency_ms"],
                    },
                    "by_domain": summary["by_domain"],
                    "misses": bench["misses"],
                },
                f,
                indent=2,
            )
        print(f"Results written to {output_path}")


if __name__ == "__main__":
    main()
