# Routing Accuracy Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone benchmark that sends 50 MMLU-style questions through the semantic router and measures whether the domain classifier routes each one to the correct backend (qwen vs llama).

**Architecture:** A static JSON dataset of 50 questions (10 per domain: math, computer_science, biology, history, geography) lives in `bench/data/routing_bench_data.json`. A single script `bench/routing/routing_bench.py` reads the dataset, sends each question to Envoy via the OpenAI client, reads `response.model` to determine which backend responded, compares to `expected_backend`, and prints a per-domain accuracy table.

**Tech Stack:** Python 3, `openai` SDK (already in `bench/requirements.txt`), `pytest`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `bench/data/routing_bench_data.json` | Create | 50 MMLU-style questions with domain + expected_backend labels |
| `bench/routing/__init__.py` | Create | Makes `routing` a Python package |
| `bench/routing/routing_bench.py` | Create | CLI entrypoint + all benchmark logic |
| `bench/routing/tests/__init__.py` | Create | Makes tests a package |
| `bench/routing/tests/test_routing_bench.py` | Create | Unit tests for pure functions |

---

### Task 1: Create the Dataset

**Files:**
- Create: `bench/data/routing_bench_data.json`

- [ ] **Step 1: Write the dataset file**

Write exactly this content to `bench/data/routing_bench_data.json`:

```json
[
  {"id":"math_001","domain":"math","expected_backend":"qwen","question":"What is the derivative of x³ with respect to x?","options":["x²","3x²","3x","2x³"],"correct_option":"B"},
  {"id":"math_002","domain":"math","expected_backend":"qwen","question":"What is the sum of interior angles of a hexagon?","options":["540°","720°","360°","900°"],"correct_option":"B"},
  {"id":"math_003","domain":"math","expected_backend":"qwen","question":"Which of the following is a prime number?","options":["51","57","59","63"],"correct_option":"C"},
  {"id":"math_004","domain":"math","expected_backend":"qwen","question":"What is log₂(8)?","options":["2","3","4","6"],"correct_option":"B"},
  {"id":"math_005","domain":"math","expected_backend":"qwen","question":"What is the solution to 2x + 6 = 14?","options":["3","4","5","7"],"correct_option":"B"},
  {"id":"math_006","domain":"math","expected_backend":"qwen","question":"What is the determinant of the matrix [[2,1],[4,3]]?","options":["2","10","6","-2"],"correct_option":"A"},
  {"id":"math_007","domain":"math","expected_backend":"qwen","question":"In a normal distribution, approximately what percentage of data falls within one standard deviation of the mean?","options":["50%","68%","95%","99.7%"],"correct_option":"B"},
  {"id":"math_008","domain":"math","expected_backend":"qwen","question":"What is the area of a circle with radius 5?","options":["25π","10π","5π","50π"],"correct_option":"A"},
  {"id":"math_009","domain":"math","expected_backend":"qwen","question":"If f(x) = eˣ, what is f'(x)?","options":["xeˣ⁻¹","eˣ","eˣ⁻¹","xeˣ"],"correct_option":"B"},
  {"id":"math_010","domain":"math","expected_backend":"qwen","question":"What is the value of the integral of sin(x) with respect to x?","options":["cos(x) + C","-cos(x) + C","sin(x) + C","-sin(x) + C"],"correct_option":"B"},

  {"id":"cs_001","domain":"computer_science","expected_backend":"qwen","question":"What data structure uses LIFO (Last In First Out) ordering?","options":["Queue","Stack","Heap","Linked List"],"correct_option":"B"},
  {"id":"cs_002","domain":"computer_science","expected_backend":"qwen","question":"What is the time complexity of binary search on a sorted array?","options":["O(n)","O(n²)","O(log n)","O(n log n)"],"correct_option":"C"},
  {"id":"cs_003","domain":"computer_science","expected_backend":"qwen","question":"In the TCP/IP model, which protocol operates at the transport layer?","options":["HTTP","IP","TCP","ARP"],"correct_option":"C"},
  {"id":"cs_004","domain":"computer_science","expected_backend":"qwen","question":"Which sorting algorithm guarantees O(n log n) worst-case time complexity?","options":["Bubble sort","Selection sort","Quicksort","Merge sort"],"correct_option":"D"},
  {"id":"cs_005","domain":"computer_science","expected_backend":"qwen","question":"In object-oriented programming, what is encapsulation?","options":["Inheriting methods from a parent class","Hiding internal state behind a public interface","Writing multiple methods with the same name","Creating objects from a class"],"correct_option":"B"},
  {"id":"cs_006","domain":"computer_science","expected_backend":"qwen","question":"What is a deadlock in concurrent programming?","options":["A memory leak","Two processes each waiting for a resource held by the other","A race condition","An infinite loop"],"correct_option":"B"},
  {"id":"cs_007","domain":"computer_science","expected_backend":"qwen","question":"Which HTTP method is both idempotent and safe?","options":["POST","PUT","DELETE","GET"],"correct_option":"D"},
  {"id":"cs_008","domain":"computer_science","expected_backend":"qwen","question":"What does a compiler do?","options":["Executes code line by line","Translates source code into machine code","Manages memory allocation","Handles network requests"],"correct_option":"B"},
  {"id":"cs_009","domain":"computer_science","expected_backend":"qwen","question":"In a relational database, what does a foreign key do?","options":["Uniquely identifies each row in its table","References the primary key of another table","Encrypts sensitive columns","Speeds up query execution"],"correct_option":"B"},
  {"id":"cs_010","domain":"computer_science","expected_backend":"qwen","question":"What is the worst-case time complexity of quicksort?","options":["O(n log n)","O(n)","O(n²)","O(log n)"],"correct_option":"C"},

  {"id":"bio_001","domain":"biology","expected_backend":"qwen","question":"Which organelle is known as the powerhouse of the cell?","options":["Nucleus","Ribosome","Mitochondria","Golgi apparatus"],"correct_option":"C"},
  {"id":"bio_002","domain":"biology","expected_backend":"qwen","question":"Which cellular process converts glucose to pyruvate?","options":["Krebs cycle","Glycolysis","Oxidative phosphorylation","Fermentation"],"correct_option":"B"},
  {"id":"bio_003","domain":"biology","expected_backend":"qwen","question":"What is the central dogma of molecular biology?","options":["DNA → RNA → Protein","RNA → DNA → Protein","Protein → RNA → DNA","DNA → Protein → RNA"],"correct_option":"A"},
  {"id":"bio_004","domain":"biology","expected_backend":"qwen","question":"What type of chemical bond holds the two strands of DNA together?","options":["Covalent bonds","Ionic bonds","Hydrogen bonds","Peptide bonds"],"correct_option":"C"},
  {"id":"bio_005","domain":"biology","expected_backend":"qwen","question":"During which phase of mitosis do chromosomes align at the cell's equator?","options":["Prophase","Metaphase","Anaphase","Telophase"],"correct_option":"B"},
  {"id":"bio_006","domain":"biology","expected_backend":"qwen","question":"What is the role of mRNA in protein synthesis?","options":["It catalyzes peptide bond formation","It carries genetic information from DNA to ribosomes","It brings amino acids to the ribosome","It forms the ribosome structure"],"correct_option":"B"},
  {"id":"bio_007","domain":"biology","expected_backend":"qwen","question":"Which organelle is responsible for protein sorting and modification?","options":["Lysosome","Peroxisome","Golgi apparatus","Smooth ER"],"correct_option":"C"},
  {"id":"bio_008","domain":"biology","expected_backend":"qwen","question":"What is natural selection?","options":["Random changes in allele frequency","Differential survival and reproduction based on heritable traits","The process of genetic mutation","Migration of individuals between populations"],"correct_option":"B"},
  {"id":"bio_009","domain":"biology","expected_backend":"qwen","question":"What molecule carries oxygen in red blood cells?","options":["Myoglobin","Ferritin","Hemoglobin","Albumin"],"correct_option":"C"},
  {"id":"bio_010","domain":"biology","expected_backend":"qwen","question":"Which blood cells are primarily responsible for the immune response?","options":["Erythrocytes","Platelets","Leukocytes","Plasma cells"],"correct_option":"C"},

  {"id":"hist_001","domain":"history","expected_backend":"llama","question":"In which year did the French Revolution begin?","options":["1776","1789","1799","1815"],"correct_option":"B"},
  {"id":"hist_002","domain":"history","expected_backend":"llama","question":"Who was the first President of the United States?","options":["John Adams","Thomas Jefferson","Benjamin Franklin","George Washington"],"correct_option":"D"},
  {"id":"hist_003","domain":"history","expected_backend":"llama","question":"What event triggered the start of World War I?","options":["The invasion of Poland","The assassination of Archduke Franz Ferdinand","The sinking of the Lusitania","The fall of the Ottoman Empire"],"correct_option":"B"},
  {"id":"hist_004","domain":"history","expected_backend":"llama","question":"Which empire was Julius Caesar a leader of?","options":["Greek Empire","Ottoman Empire","Roman Empire","Byzantine Empire"],"correct_option":"C"},
  {"id":"hist_005","domain":"history","expected_backend":"llama","question":"Who wrote the Communist Manifesto?","options":["Vladimir Lenin","Leon Trotsky","Karl Marx and Friedrich Engels","Joseph Stalin"],"correct_option":"C"},
  {"id":"hist_006","domain":"history","expected_backend":"llama","question":"The Renaissance began in which country?","options":["France","Germany","England","Italy"],"correct_option":"D"},
  {"id":"hist_007","domain":"history","expected_backend":"llama","question":"Which treaty formally ended World War I?","options":["Treaty of Paris","Treaty of Versailles","Treaty of Utrecht","Treaty of Westphalia"],"correct_option":"B"},
  {"id":"hist_008","domain":"history","expected_backend":"llama","question":"What was the name of the first artificial satellite launched into space?","options":["Explorer 1","Vostok 1","Sputnik 1","Apollo 1"],"correct_option":"C"},
  {"id":"hist_009","domain":"history","expected_backend":"llama","question":"What was the primary cause of the American Civil War?","options":["Economic differences between North and South","The issue of slavery and its expansion","Taxation disputes","British interference in American politics"],"correct_option":"B"},
  {"id":"hist_010","domain":"history","expected_backend":"llama","question":"Which document established the Magna Carta principles of limiting royal power?","options":["The Magna Carta of 1215","The Bill of Rights of 1689","The Petition of Right of 1628","The Act of Settlement of 1701"],"correct_option":"A"},

  {"id":"geo_001","domain":"geography","expected_backend":"llama","question":"What is the largest continent by land area?","options":["Africa","North America","Asia","Europe"],"correct_option":"C"},
  {"id":"geo_002","domain":"geography","expected_backend":"llama","question":"Which river is the longest in the world?","options":["Amazon","Yangtze","Mississippi","Nile"],"correct_option":"D"},
  {"id":"geo_003","domain":"geography","expected_backend":"llama","question":"What is the capital of Australia?","options":["Sydney","Melbourne","Canberra","Brisbane"],"correct_option":"C"},
  {"id":"geo_004","domain":"geography","expected_backend":"llama","question":"Which ocean is the largest by surface area?","options":["Atlantic Ocean","Indian Ocean","Arctic Ocean","Pacific Ocean"],"correct_option":"D"},
  {"id":"geo_005","domain":"geography","expected_backend":"llama","question":"The Sahara Desert is located on which continent?","options":["Asia","Australia","Africa","South America"],"correct_option":"C"},
  {"id":"geo_006","domain":"geography","expected_backend":"llama","question":"What is the smallest country in the world by area?","options":["Monaco","San Marino","Liechtenstein","Vatican City"],"correct_option":"D"},
  {"id":"geo_007","domain":"geography","expected_backend":"llama","question":"Which mountain range separates Europe from Asia?","options":["Alps","Himalayas","Ural Mountains","Caucasus Mountains"],"correct_option":"C"},
  {"id":"geo_008","domain":"geography","expected_backend":"llama","question":"What is the capital of Brazil?","options":["São Paulo","Rio de Janeiro","Brasília","Salvador"],"correct_option":"C"},
  {"id":"geo_009","domain":"geography","expected_backend":"llama","question":"What is the deepest lake in the world?","options":["Lake Superior","Caspian Sea","Lake Baikal","Lake Tanganyika"],"correct_option":"C"},
  {"id":"geo_010","domain":"geography","expected_backend":"llama","question":"Which country has the most natural freshwater resources?","options":["United States","China","Russia","Brazil"],"correct_option":"D"}
]
```

- [ ] **Step 2: Verify the file has exactly 50 records**

```bash
python3 -c "import json; d=json.load(open('bench/data/routing_bench_data.json')); print(len(d), 'questions'); domains={}; [domains.update({q['domain']:domains.get(q['domain'],0)+1}) for q in d]; print(domains)"
```

Expected:
```
50 questions
{'math': 10, 'computer_science': 10, 'biology': 10, 'history': 10, 'geography': 10}
```

- [ ] **Step 3: Commit the dataset**

```bash
git add bench/data/routing_bench_data.json
git commit -m "feat: add MMLU-style routing benchmark dataset (50 questions, 5 domains)"
```

---

### Task 2: Create Package Skeleton and Write Tests

**Files:**
- Create: `bench/routing/__init__.py`
- Create: `bench/routing/tests/__init__.py`
- Create: `bench/routing/tests/test_routing_bench.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p bench/routing/tests
touch bench/routing/__init__.py
touch bench/routing/tests/__init__.py
```

- [ ] **Step 2: Write the test file**

Write this content to `bench/routing/tests/test_routing_bench.py`:

```python
"""Unit tests for routing_bench pure functions."""

import json
import os
import tempfile

import pytest

from routing.routing_bench import (
    compute_summary,
    detect_backend,
    format_question,
    load_questions,
)


# ---------------------------------------------------------------------------
# detect_backend
# ---------------------------------------------------------------------------

def test_detect_backend_qwen():
    assert detect_backend("qwen2.5:3b", "qwen2.5:3b", "tinyllama") == "qwen"


def test_detect_backend_llama():
    assert detect_backend("tinyllama", "qwen2.5:3b", "tinyllama") == "llama"


def test_detect_backend_unknown():
    assert detect_backend("some-other-model", "qwen2.5:3b", "tinyllama") == "unknown"


def test_detect_backend_exact_match_only():
    # Partial match must not succeed
    assert detect_backend("qwen2.5:3b-extra", "qwen2.5:3b", "tinyllama") == "unknown"


# ---------------------------------------------------------------------------
# format_question
# ---------------------------------------------------------------------------

def test_format_question_contains_question_text():
    q = {
        "question": "What is 2 + 2?",
        "options": ["3", "4", "5", "6"],
    }
    result = format_question(q)
    assert "What is 2 + 2?" in result


def test_format_question_contains_all_options():
    q = {
        "question": "Which is prime?",
        "options": ["4", "7", "9", "15"],
    }
    result = format_question(q)
    assert "A)" in result
    assert "B)" in result
    assert "C)" in result
    assert "D)" in result
    assert "4" in result
    assert "7" in result


def test_format_question_option_letters_in_order():
    q = {
        "question": "Pick one.",
        "options": ["alpha", "beta", "gamma", "delta"],
    }
    result = format_question(q)
    a_pos = result.index("A)")
    b_pos = result.index("B)")
    c_pos = result.index("C)")
    d_pos = result.index("D)")
    assert a_pos < b_pos < c_pos < d_pos


# ---------------------------------------------------------------------------
# load_questions
# ---------------------------------------------------------------------------

SAMPLE_DATA = [
    {"id": "math_001", "domain": "math", "expected_backend": "qwen",
     "question": "Q1", "options": ["A", "B"], "correct_option": "A"},
    {"id": "math_002", "domain": "math", "expected_backend": "qwen",
     "question": "Q2", "options": ["A", "B"], "correct_option": "B"},
    {"id": "hist_001", "domain": "history", "expected_backend": "llama",
     "question": "Q3", "options": ["A", "B"], "correct_option": "A"},
]


def test_load_questions_returns_all_without_limit(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps(SAMPLE_DATA))
    questions = load_questions(str(data_file), samples_per_domain=None)
    assert len(questions) == 3


def test_load_questions_respects_samples_per_domain(tmp_path):
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps(SAMPLE_DATA))
    questions = load_questions(str(data_file), samples_per_domain=1)
    domains = [q["domain"] for q in questions]
    assert domains.count("math") == 1
    assert domains.count("history") == 1


def test_load_questions_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_questions("/nonexistent/path/data.json", samples_per_domain=None)


# ---------------------------------------------------------------------------
# compute_summary
# ---------------------------------------------------------------------------

def test_compute_summary_all_correct():
    results = [
        {"domain": "math", "expected": "qwen", "correct": True},
        {"domain": "math", "expected": "qwen", "correct": True},
        {"domain": "history", "expected": "llama", "correct": True},
    ]
    summary = compute_summary(results)
    assert summary["total"] == 3
    assert summary["correct"] == 3
    assert summary["accuracy"] == 1.0
    assert summary["by_domain"]["math"]["accuracy"] == 1.0
    assert summary["by_domain"]["history"]["accuracy"] == 1.0


def test_compute_summary_partial_correct():
    results = [
        {"domain": "math", "expected": "qwen", "correct": True},
        {"domain": "math", "expected": "qwen", "correct": False},
        {"domain": "history", "expected": "llama", "correct": True},
    ]
    summary = compute_summary(results)
    assert summary["total"] == 3
    assert summary["correct"] == 2
    assert abs(summary["accuracy"] - 2 / 3) < 1e-9
    assert summary["by_domain"]["math"]["correct"] == 1
    assert summary["by_domain"]["math"]["total"] == 2
    assert abs(summary["by_domain"]["math"]["accuracy"] - 0.5) < 1e-9


def test_compute_summary_empty():
    summary = compute_summary([])
    assert summary["total"] == 0
    assert summary["correct"] == 0
    assert summary["accuracy"] == 0.0


def test_compute_summary_preserves_expected_backend():
    results = [
        {"domain": "biology", "expected": "qwen", "correct": True},
    ]
    summary = compute_summary(results)
    assert summary["by_domain"]["biology"]["expected"] == "qwen"
```

- [ ] **Step 3: Run the tests — verify they all fail (functions not yet implemented)**

```bash
cd bench && python3 -m pytest routing/tests/test_routing_bench.py -v 2>&1 | head -30
```

Expected: `ImportError` or `ModuleNotFoundError` — `routing.routing_bench` doesn't exist yet.

- [ ] **Step 4: Commit the test file and package skeleton**

```bash
git add bench/routing/__init__.py bench/routing/tests/__init__.py bench/routing/tests/test_routing_bench.py
git commit -m "test: add routing benchmark unit tests (all failing)"
```

---

### Task 3: Implement routing_bench.py

**Files:**
- Create: `bench/routing/routing_bench.py`

- [ ] **Step 1: Write the implementation**

Write this content to `bench/routing/routing_bench.py`:

```python
"""
Routing Accuracy Benchmark

Sends MMLU-style questions through the semantic router and measures whether
the domain classifier routes each question to the correct backend.

Usage:
    cd bench
    python3 -m routing.routing_bench \\
        --endpoint http://127.0.0.1:8801/v1 \\
        --qwen-model "qwen2.5:3b" \\
        --llama-model "tinyllama"
"""

import argparse
import json
import os
import sys
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
        try:
            response = client.chat.completions.create(
                model="auto",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
            )
            got_model = response.model
        except Exception as exc:
            got_model = f"error:{exc}"

        got_backend = detect_backend(got_model, qwen_model, llama_model)
        correct = got_backend == q["expected_backend"]

        result = {
            "id": q["id"],
            "domain": q["domain"],
            "expected": q["expected_backend"],
            "got": got_backend,
            "got_model": got_model,
            "correct": correct,
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

    for stats in by_domain.values():
        stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0

    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    return {
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0.0,
        "by_domain": by_domain,
    }


def print_table(summary: Dict[str, Any]) -> None:
    """Print the routing accuracy table to stdout."""
    sep = "─" * 56
    print(f"\n{'Domain':<20} {'Expected':<10} {'Correct':<9} {'Total':<7} Accuracy")
    print(sep)
    for domain, stats in sorted(summary["by_domain"].items()):
        print(
            f"{domain:<20} {stats['expected']:<10} {stats['correct']:<9}"
            f" {stats['total']:<7} {stats['accuracy'] * 100:.1f}%"
        )
    print(sep)
    print(
        f"{'OVERALL':<20} {'':<10} {summary['correct']:<9}"
        f" {summary['total']:<7} {summary['accuracy'] * 100:.1f}%"
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
```

- [ ] **Step 2: Run the unit tests — verify they all pass**

```bash
cd bench && python3 -m pytest routing/tests/test_routing_bench.py -v
```

Expected output (all green):
```
test_routing_bench.py::test_detect_backend_qwen PASSED
test_routing_bench.py::test_detect_backend_llama PASSED
test_routing_bench.py::test_detect_backend_unknown PASSED
test_routing_bench.py::test_detect_backend_exact_match_only PASSED
test_routing_bench.py::test_format_question_contains_question_text PASSED
test_routing_bench.py::test_format_question_contains_all_options PASSED
test_routing_bench.py::test_format_question_option_letters_in_order PASSED
test_routing_bench.py::test_load_questions_returns_all_without_limit PASSED
test_routing_bench.py::test_load_questions_respects_samples_per_domain PASSED
test_routing_bench.py::test_load_questions_file_not_found PASSED
test_routing_bench.py::test_compute_summary_all_correct PASSED
test_routing_bench.py::test_compute_summary_partial_correct PASSED
test_routing_bench.py::test_compute_summary_empty PASSED
test_routing_bench.py::test_compute_summary_preserves_expected_backend PASSED

14 passed in 0.XXs
```

If any test fails, check that the function signatures and field names in `routing_bench.py` exactly match the test expectations above.

- [ ] **Step 3: Commit the implementation**

```bash
git add bench/routing/routing_bench.py
git commit -m "feat: implement routing accuracy benchmark script"
```

---

### Task 4: Smoke Test Against Mock Backends

**Files:** none modified

This task verifies the end-to-end flow using two mock-vllm processes. The mock-vllm at `tools/mock-vllm/app.py` echoes back the model name it receives, which is exactly what `detect_backend` reads.

- [ ] **Step 1: Start two mock-vllm instances in separate terminals**

Terminal 1 (qwen backend on port 8000):
```bash
cd tools/mock-vllm
pip install fastapi uvicorn -q
python3 app.py
```

Expected: `Uvicorn running on http://0.0.0.0:8000`

Terminal 2 (llama backend on port 8001):
```bash
cd tools/mock-vllm
uvicorn app:app --host 0.0.0.0 --port 8001
```

Expected: `Uvicorn running on http://0.0.0.0:8001`

- [ ] **Step 2: Start the router**

In a third terminal (keep running):
```bash
scripts/local-up-router.sh
```

Expected: `The local semantic router is running.`

- [ ] **Step 3: Run the benchmark**

```bash
cd bench && python3 -m routing.routing_bench \
  --endpoint http://127.0.0.1:8801/v1 \
  --qwen-model "qwen2.5:3b" \
  --llama-model "tinyllama" \
  --samples-per-domain 3
```

Expected: a table printed to stdout showing per-domain routing accuracy. Any non-zero accuracy confirms the pipeline is working. `domain=[]` in router logs means the classifier isn't running — check Task 2 in `docs/superpowers/plans/2026-04-01-domain-classifier-routing.md`.

- [ ] **Step 4: Verify the JSON output option works**

```bash
cd bench && python3 -m routing.routing_bench \
  --endpoint http://127.0.0.1:8801/v1 \
  --qwen-model "qwen2.5:3b" \
  --llama-model "tinyllama" \
  --samples-per-domain 2 \
  --output-dir /tmp/routing_results

cat /tmp/routing_results/routing_results.json
```

Expected: valid JSON with keys `summary`, `by_domain`, `misses`.

- [ ] **Step 5: Commit smoke test confirmation**

```bash
git add bench/routing/routing_bench.py bench/routing/__init__.py bench/routing/tests/
git commit -m "feat: routing accuracy benchmark complete and smoke-tested

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
