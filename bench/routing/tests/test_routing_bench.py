"""Unit tests for routing_bench pure functions."""

import json

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
