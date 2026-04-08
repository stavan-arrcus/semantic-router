"""
Classifier Benchmark (CPU/GPU)

Runs routing benchmark questions directly through the domain classifier model,
bypassing Envoy and the router binary. Useful for measuring classifier accuracy
and latency on different hardware (CPU vs GPU).

Usage:
    # Local CPU (uses models/mom-domain-classifier)
    python3 classifier_bench.py

    # Colab/GPU (upload model dir and data file first)
    python3 classifier_bench.py \
        --model-path /content/mom-domain-classifier \
        --data /content/routing_bench_data.json

    # Custom threshold
    python3 classifier_bench.py --threshold 0.4
"""

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import torch
from transformers import BertForSequenceClassification, BertTokenizer


# Domains that route to qwen; everything else routes to llama (default)
QWEN_DOMAINS = {"math", "computer science", "biology"}
LLAMA_DOMAINS = {"history", "psychology", "philosophy"}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark domain classifier accuracy and latency directly (no router/Envoy)"
    )
    parser.add_argument(
        "--model-path",
        default=os.path.join(os.path.dirname(__file__), "..", "..", "models", "mom-domain-classifier"),
        help="Path to domain classifier model directory",
    )
    parser.add_argument(
        "--mapping-path",
        default=None,
        help="Path to category_mapping.json (default: <model-path>/category_mapping.json)",
    )
    parser.add_argument(
        "--data",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "routing_bench_data.json"),
        help="Path to routing_bench_data.json",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.6,
        help="Confidence threshold — below this routes to default/llama (default: 0.6)",
    )
    parser.add_argument(
        "--samples-per-domain",
        type=int,
        default=None,
        help="Limit questions per domain (default: use all)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent classification requests (default: 1 = sequential)",
    )
    return parser.parse_args()


def load_model(model_path: str) -> Tuple[Any, Any, str]:
    """Load the classifier model and tokenizer, auto-detecting device."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    if device == "cuda":
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    tokenizer = BertTokenizer.from_pretrained(model_path)
    model = BertForSequenceClassification.from_pretrained(model_path, num_labels=14)
    model.to(device)
    model.eval()
    return model, tokenizer, device


def classify(
    model: Any,
    tokenizer: Any,
    idx_to_category: Dict[int, str],
    text: str,
    threshold: float,
    device: str,
) -> Tuple[Optional[str], float]:
    """
    Classify text and return (category, confidence).
    Returns (None, confidence) if confidence is below threshold.
    """
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)
    confidence, idx = torch.max(probs, dim=-1)
    confidence = confidence.item()
    if confidence < threshold:
        return None, confidence
    return idx_to_category[idx.item()], confidence


def domain_to_backend(domain: Optional[str]) -> str:
    """Map classifier output domain to backend label."""
    if domain is None:
        return "llama"  # below threshold → default
    if domain in QWEN_DOMAINS:
        return "qwen"
    if domain in LLAMA_DOMAINS:
        return "llama"
    return "llama"  # everything else (geography, other, etc.) → default


def load_questions(data_path: str, samples_per_domain: Optional[int]) -> List[Dict[str, Any]]:
    with open(data_path) as f:
        questions = json.load(f)
    if samples_per_domain is None:
        return questions
    by_domain: Dict[str, List] = {}
    for q in questions:
        by_domain.setdefault(q["domain"], []).append(q)
    result = []
    for dqs in by_domain.values():
        result.extend(dqs[:samples_per_domain])
    return result


def classify_question(
    q: Dict[str, Any],
    model: Any,
    tokenizer: Any,
    idx_to_category: Dict[int, str],
    threshold: float,
    device: str,
) -> Dict[str, Any]:
    """Classify a single question and return a result dict."""
    t0 = time.time()
    domain, confidence = classify(model, tokenizer, idx_to_category, q["question"], threshold, device)
    latency_ms = (time.time() - t0) * 1000

    got_backend = domain_to_backend(domain)
    correct = got_backend == q["expected_backend"]

    return {
        "id": q["id"],
        "domain": q["domain"],
        "expected": q["expected_backend"],
        "got": got_backend,
        "classified_as": domain if domain else f"<below threshold:{confidence:.2f}>",
        "confidence": confidence,
        "correct": correct,
        "latency_ms": latency_ms,
        "question": q["question"],
    }


def run_benchmark(
    questions: List[Dict[str, Any]],
    model: Any,
    tokenizer: Any,
    idx_to_category: Dict[int, str],
    threshold: float,
    device: str,
    concurrency: int = 1,
) -> Dict[str, Any]:
    wall_start = time.time()

    if concurrency == 1:
        results = [classify_question(q, model, tokenizer, idx_to_category, threshold, device) for q in questions]
    else:
        results = [None] * len(questions)
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(classify_question, q, model, tokenizer, idx_to_category, threshold, device): i
                for i, q in enumerate(questions)
            }
            for future in as_completed(futures):
                results[futures[future]] = future.result()

    wall_ms = (time.time() - wall_start) * 1000
    throughput = len(questions) / (wall_ms / 1000)

    misses = []
    for r in results:
        if not r["correct"]:
            misses.append(r)
            print(f"MISS [{r['id']}] expected={r['expected']} got={r['got']} "
                  f"(classified_as={r['classified_as']} conf={r['confidence']:.2f})")
            print(f"  \"{r['question']}\"")

    return {"results": results, "misses": misses, "wall_ms": wall_ms, "throughput_rps": throughput}


def compute_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_domain: Dict[str, Any] = {}
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
        stats["avg_confidence"] = sum(r["confidence"] for r in domain_results) / len(domain_results)

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0.0,
        "avg_latency_ms": sum(r["latency_ms"] for r in results) / total if total > 0 else 0.0,
        "by_domain": by_domain,
    }


def print_table(summary: Dict[str, Any], device: str, threshold: float, concurrency: int, throughput_rps: float, wall_ms: float) -> None:
    sep = "─" * 80
    print(f"\nDevice: {device}  |  Threshold: {threshold}  |  Concurrency: {concurrency}")
    print(f"Throughput: {throughput_rps:.1f} req/s  |  Wall time: {wall_ms:.0f}ms")
    print(f"\n{'Domain':<20} {'Expected':<10} {'Correct':<9} {'Total':<7} {'Accuracy':<12} {'Avg Conf':<10} Avg Latency")
    print(sep)
    for domain, stats in sorted(summary["by_domain"].items()):
        print(
            f"{domain:<20} {stats['expected']:<10} {stats['correct']:<9}"
            f" {stats['total']:<7} {stats['accuracy'] * 100:.1f}%{'':9}"
            f" {stats['avg_confidence']:.2f}{'':6} {stats['avg_latency_ms']:.1f}ms"
        )
    print(sep)
    print(
        f"{'OVERALL':<20} {'':<10} {summary['correct']:<9}"
        f" {summary['total']:<7} {summary['accuracy'] * 100:.1f}%{'':9}"
        f" {'':10} {summary['avg_latency_ms']:.1f}ms"
    )
    print()


def main() -> None:
    args = parse_args()

    model_path = os.path.abspath(args.model_path)
    mapping_path = args.mapping_path or os.path.join(model_path, "category_mapping.json")
    data_path = os.path.abspath(args.data)

    for path, label in [(model_path, "model"), (mapping_path, "mapping"), (data_path, "data")]:
        if not os.path.exists(path):
            print(f"Error: {label} not found: {path}")
            raise SystemExit(1)

    with open(mapping_path) as f:
        mapping = json.load(f)
    idx_to_category = {int(k): v for k, v in mapping["idx_to_category"].items()}

    print(f"Loading model from {model_path} ...")
    model, tokenizer, device = load_model(model_path)

    questions = load_questions(data_path, args.samples_per_domain)
    print(f"Loaded {len(questions)} questions\n")

    bench = run_benchmark(questions, model, tokenizer, idx_to_category, args.threshold, device, args.concurrency)
    summary = compute_summary(bench["results"])
    print_table(summary, device, args.threshold, args.concurrency, bench["throughput_rps"], bench["wall_ms"])


if __name__ == "__main__":
    main()
