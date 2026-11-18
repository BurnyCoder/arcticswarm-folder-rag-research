"""Offline tests for the folder-RAG harness (no API calls, no WSL needed).

Covers: sampling (largest-remainder quotas, seeded stratified ordering, quota take),
answer extraction and the deterministic metrics, the pre-registered statistics
(Wilson interval, exact McNemar, Holm), and cost accounting.
"""

from __future__ import annotations

import math

import numpy as np

from folderrag.analyze import bootstrap_diff, holm, mcnemar_exact, wilson
from folderrag.collect import case_cost
from folderrag.datasets import largest_remainder, stratified_order, take_quota
from folderrag.judge import exact_match, extract_final, normalize, official_overlap


def test_largest_remainder_matches_amendment():
    counts = {"comparison_query": 856, "inference_query": 816, "null_query": 301, "temporal_query": 583}
    assert largest_remainder(counts, 10) == {"comparison_query": 4, "inference_query": 3, "null_query": 1, "temporal_query": 2}
    assert sum(largest_remainder(counts, 150).values()) == 150


def test_stratified_order_is_seeded_and_interleaved():
    items = [{"id": i, "s": "a" if i < 50 else "b"} for i in range(100)]
    o1, o2 = stratified_order(items, "s"), stratified_order(items, "s")
    assert [x["id"] for x in o1] == [x["id"] for x in o2]  # deterministic
    first10 = Counter_s(o1[:10])
    assert abs(first10["a"] - first10["b"]) <= 2  # proportional interleaving
    took = take_quota(o1, "s", {"a": 3, "b": 1})
    assert Counter_s(took) == {"a": 3, "b": 1}


def Counter_s(rows):
    out = {}
    for r in rows:
        out[r["s"]] = out.get(r["s"], 0) + 1
    return out


def test_extract_final_takes_last_and_strips_markup():
    text = "draft FINAL ANSWER: no\n...\n**FINAL ANSWER: Sam Bankman-Fried**"
    assert extract_final(text) == "Sam Bankman-Fried"
    assert extract_final("no marker here") == ""


def test_exact_match_rules():
    assert exact_match("Yes, both report it.", "Yes")
    assert not exact_match("No", "Yes")
    assert exact_match("Insufficient information to answer", "Insufficient information.")
    assert exact_match("the Federal Reserve", "Federal Reserve")
    assert not exact_match("", "Yes")
    assert normalize("The  F.E.D.!") == "fed"


def test_official_overlap_is_gameable():
    # The MultiHop-RAG word-overlap metric accepts a hedge containing the gold word.
    assert official_overlap("yes no insufficient information", "Yes")
    assert official_overlap("yes no insufficient information", "Insufficient information.")


def test_wilson_and_holm_and_mcnemar():
    lo, hi = wilson(7, 10)
    assert 0.39 < lo < 0.40 and 0.89 < hi < 0.90  # standard Wilson values for 7/10
    assert holm({"H1": 0.01, "H3": 0.04}) == {"H1": 0.02, "H3": 0.04}
    r = mcnemar_exact([True] * 6 + [False] * 4, [False] * 6 + [False] * 4)
    assert r["x_only"] == 6 and r["y_only"] == 0 and math.isclose(r["p"], 2 * 0.5 ** 6)
    lo, hi = bootstrap_diff(np.ones(10), np.zeros(10))
    assert lo == hi == 1.0


def test_case_cost_uses_haiku_short_card():
    # 1M input + 1M output + 1M cache read + 1M cache write at $0.10/$0.50/$0.01/$0.125
    assert math.isclose(case_cost({"input": 1e6, "output": 1e6, "cache_read": 1e6, "cache_creation": 1e6}), 0.735)
    assert math.isclose(case_cost({"input_tokens": 1e6, "output_tokens": 1e6, "cache_read_input_tokens": 1e6,
                                   "cache_creation_input_tokens": 1e6}), 0.735)
