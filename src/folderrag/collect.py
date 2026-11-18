"""Collect per-question outcomes from ArcticSwarm run dirs and judge them uniformly.

Global context: ``folderrag run`` leaves, per condition and folder, an ArcticSwarm
output dir with ``report.json`` (per-case response, tokens, latency, tool calls) and
``trajectories/<id>.json``. This module flattens them into one row per
(condition, question), adds cost and MultiHop-RAG gold-evidence recall, runs the
unified judge (``folderrag.judge``) and writes ``results/<tag>/judged.jsonl``.
Every number downstream (tables, figures, paper) is computed from that file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from folderrag.judge import judge_rows
from folderrag.run import load_sample
from folderrag.settings import LOGS_DIR, PRICE, PRICE_LONG, RESULTS_DIR, RUNS_DIR

log = logging.getLogger(__name__)
LONG_PROMPT = 100_000  # Haiku 5.5 switches to the higher rate card above this prompt size


def case_cost(tok: dict[str, Any]) -> float:
    """$ from report.json token_usage at the <=100K-prompt rate card (lower bound)."""
    g = lambda *ks: next((tok[k] for k in ks if k in tok), 0)  # noqa: E731  (report.json uses *_tokens keys)
    return (
        g("input_tokens", "input") * PRICE["input"] + g("output_tokens", "output") * PRICE["output"]
        + g("cache_read_input_tokens", "cache_read") * PRICE["cache_read"]
        + g("cache_creation_input_tokens", "cache_creation") * PRICE["cache_write"]
    ) / 1e6


def tool_counts(case: dict[str, Any], traj: Path) -> dict[str, int]:
    """Tool calls by name: swarm subagents' persistent counters, else trajectory tool_use blocks."""
    counts: dict[str, int] = {}
    sub = case.get("swarm_subagent_tool_counts") or {}
    for agent_counts in sub.values():
        for name, n in agent_counts.items():
            counts[name] = counts.get(name, 0) + int(n)
    if counts or not traj.exists():
        return counts

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            if o.get("type") == "tool_use" and isinstance(o.get("name"), str):
                counts[o["name"]] = counts.get(o["name"], 0) + 1
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(traj.read_text(encoding="utf-8", errors="replace")))
    return counts


def log_cost(path: Path) -> dict[str, float]:
    """Exact run cost from the LLM call log, applying the >100K-token rate card per call."""
    total, calls, long_calls = 0.0, 0, 0
    if not path.exists():
        return {"usd": 0.0, "calls": 0, "long_prompt_calls": 0}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            u = json.loads(line).get("usage") or {}
            inp, out = u.get("input_tokens", 0), u.get("output_tokens", 0)
            cr, cw = u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0)
            price = PRICE_LONG if inp + cr + cw > LONG_PROMPT else PRICE
            long_calls += price is PRICE_LONG
            total += (inp * price["input"] + out * price["output"] + cr * price["cache_read"]
                      + cw * price["cache_write"]) / 1e6
            calls += 1
    return {"usd": round(total, 4), "calls": calls, "long_prompt_calls": long_calls}


def evidence_recall(traj: Path, gold_files: list[str]) -> float | None:
    """Fraction of gold evidence file paths that appear anywhere in the trajectory."""
    if not gold_files or not traj.exists():
        return None
    text = traj.read_text(encoding="utf-8", errors="replace")
    return sum(1 for g in gold_files if g in text) / len(gold_files)


def collect_tag(tag: str) -> list[dict[str, Any]]:
    """One row per (condition, question id) found under runs/<tag>/."""
    sample = {r["id"]: r for r in load_sample()}
    rows: list[dict[str, Any]] = []
    for meta_path in sorted((RUNS_DIR / tag).glob("*/*/harness_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        run_dir = meta_path.parent
        report = run_dir / "report.json"
        per_case = {c.get("conv_id") or c.get("id"): c for c in
                    (json.loads(report.read_text(encoding="utf-8")).get("per_case", []) if report.exists() else [])}
        run_cost = log_cost(Path(meta["llm_log"]))
        for qid in meta["ids"]:
            q = sample[qid]
            c = per_case.get(qid, {})
            tok = c.get("token_usage") or {}
            rows.append({
                "condition": meta["condition"], "id": qid, "dataset": q["dataset"], "folder": q["folder"],
                "stratum": q["stratum"], "question": q["question"], "answer": q["answer"],
                "response": c.get("response_text", "") or "",
                "error": c.get("error") or ("missing from report" if not c else ""),
                "duration_s": c.get("duration_seconds"), "num_tool_calls": c.get("num_tool_calls"),
                "tool_calls": tool_counts(c, run_dir / "trajectories" / f"{qid}.json"),
                "tokens": tok, "cost_usd": round(case_cost(tok), 4),
                "evidence_recall": evidence_recall(run_dir / "trajectories" / f"{qid}.json", q["gold_files"]),
                "run_cost_usd_from_log": run_cost["usd"], "run_long_prompt_calls": run_cost["long_prompt_calls"],
                "sandbox_after_run": meta.get("sandbox_corpus_after_run"),
            })
    return rows


def judge_tag(tag: str) -> Path:
    rows = collect_tag(tag)
    judged = judge_rows(rows)
    out = RESULTS_DIR / tag / "judged.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for r in judged:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("wrote %d judged rows -> %s", len(judged), out)
    return out
