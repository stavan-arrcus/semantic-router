# Routing Accuracy Benchmark — Design Spec

**Date:** 2026-04-01
**Branch:** vLLM-scalability-test
**Status:** Approved

## Problem

There is no automated way to verify that the domain classifier routes questions to the correct backend. The existing `router_reason_bench_multi_dataset.py` measures LLM answer quality, not routing decisions. A focused routing benchmark is needed to confirm the classifier is doing its job.

## Goal

Send MMLU-style questions through Envoy, detect which backend handled each one from the `model` field in the response, compare to the expected backend, and report per-domain routing accuracy.

## Routing Table (from config/config.yaml)

| Domain          | Expected Backend | Model         |
|-----------------|-----------------|---------------|
| math            | qwen            | qwen2.5:3b    |
| computer_science| qwen            | qwen2.5:3b    |
| biology         | qwen            | qwen2.5:3b    |
| history         | llama           | tinyllama     |
| geography       | llama (default) | tinyllama     |

Geography note: the domain classifier emits MMLU labels; geography questions have no matching decision and fall to `default_model: "tinyllama"`.

## New Files

```
bench/
  data/
    routing_bench_data.json     # static MMLU-style questions (50 total, 10 per domain)
  routing/
    __init__.py
    routing_bench.py            # standalone benchmark script
```

No existing files are modified.

## Data Format

`bench/data/routing_bench_data.json` — 50 records, 10 per domain:

```json
{
  "id": "math_001",
  "domain": "math",
  "expected_backend": "qwen",
  "question": "What is the derivative of x² with respect to x?",
  "options": ["x", "2x", "2x²", "x² + C"],
  "correct_option": "B"
}
```

- `correct_option` is included for MMLU authenticity but is never evaluated.
- `expected_backend` is either `"qwen"` or `"llama"`.

## How Routing is Detected

The script sends the question text as a user message to the Envoy endpoint via the OpenAI client. The router selects a backend based on the domain classifier output. The backend's response includes a `model` field — mock-vllm echoes back the model name the router forwarded. The script maps that to a backend:

- `response.model == qwen-model-arg` → `"qwen"`
- `response.model == llama-model-arg` → `"llama"`
- anything else → `"unknown"` (counted as miss)

No log scraping, no custom headers.

## CLI

```bash
python3 -m routing.routing_bench \
  --endpoint http://127.0.0.1:8801/v1 \
  --api-key 1234 \
  --qwen-model "qwen2.5:3b" \
  --llama-model "tinyllama" \
  [--data bench/data/routing_bench_data.json] \
  [--samples-per-domain 10] \
  [--output-dir results/]
```

All flags have sensible defaults matching the current config.

## Output

Stdout table after all questions complete:

```
Domain           Expected   Correct   Total   Accuracy
──────────────────────────────────────────────────────
math             qwen        9        10       90.0%
computer_science qwen        8        10       80.0%
biology          qwen       10        10      100.0%
history          llama        9        10       90.0%
geography        llama        7        10       70.0%
──────────────────────────────────────────────────────
OVERALL                      43        50       86.0%
```

Misrouted questions print inline immediately:

```
MISS [geography_003] expected=llama got=qwen
  "What is the capital of France?"
```

If `--output-dir` is passed, writes `routing_results.json` with per-question detail:

```json
{
  "summary": { "total": 50, "correct": 43, "accuracy": 0.86 },
  "by_domain": { "math": { "correct": 9, "total": 10, "accuracy": 0.9 }, ... },
  "misses": [
    { "id": "geography_003", "domain": "geography", "expected": "llama",
      "got": "qwen", "question": "What is the capital of France?" }
  ]
}
```

## Success Criteria

- Overall routing accuracy ≥ 70% on the 50-question dataset
- math, computer_science, biology all route to qwen at ≥ 70%
- history routes to llama at ≥ 70%
- geography routes to llama (via default) at ≥ 50% (lower bar: classifier may tag some as history or other)
