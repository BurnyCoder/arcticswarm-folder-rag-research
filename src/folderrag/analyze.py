"""Metrics, pre-registered tests, tables and figures from ``results/<tag>/judged.jsonl``.

Global context: implements the analysis plan of reports/preregistration.md §5–6 so
that every number in the README/paper comes from this one script:
``folderrag analyze --tag day1`` regenerates ``metrics.json``, ``tables.md`` and the
figures under ``results/<tag>/``.

Statistics (all grounded in SciPy):
* Wilson score interval for accuracies (Wilson 1927) — computed in closed form.
* Exact McNemar test = two-sided binomial test on discordant pairs
  (``scipy.stats.binomtest``), for paired binary outcomes (H1).
* Wilcoxon signed-rank test (``scipy.stats.wilcoxon``) for paired SWE-QA scores (H3).
* Paired bootstrap 95% CI of the mean difference (10,000 resamples, seed 0).
* Holm step-down correction across the day-1 family {H1, H3}.
* T0 trivial MultiHop-RAG baselines (majority answer per question type; constant hedge
  string), scored with the official word-overlap metric and normalized EM — no API calls.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from folderrag.judge import exact_match, official_overlap
from folderrag.settings import EVAL_DIR, RESULTS_DIR

def agent_cap(cond: str) -> int:
    """Max subagents per arm: B2 = 1 (single agent), M = 16 (ArcticSwarm default), M_capN = N."""
    if cond == "B2":
        return 1
    if cond == "M":
        return 16
    return int(cond[5:]) if cond.startswith("M_cap") else 0


def label(cond: str) -> str:
    return {"M": "Swarm cap 16 (M)", "B2": "Single agent (B2)"}.get(cond, f"Swarm cap {agent_cap(cond)}")


def ordered(conds) -> list[str]:
    return sorted(conds, key=agent_cap)


PALETTE = ["#e07b39", "#9ecae1", "#6baed6", "#3182bd", "#2a6fdb", "#08519c"]


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score 95% interval for k successes out of n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_diff(a: np.ndarray, b: np.ndarray, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """Paired bootstrap 95% CI of mean(a - b)."""
    rng = np.random.default_rng(seed)
    d = a - b
    idx = rng.integers(0, len(d), size=(n_boot, len(d)))
    means = d[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def bootstrap_mean(a: np.ndarray, n_boot: int = 10_000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n_boot, len(a)))
    m = a[idx].mean(axis=1)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def mcnemar_exact(x: list[bool], y: list[bool]) -> dict[str, Any]:
    """Exact two-sided McNemar test (binomial test on discordant pairs)."""
    b = sum(1 for i, j in zip(x, y) if i and not j)  # x right, y wrong
    c = sum(1 for i, j in zip(x, y) if j and not i)
    p = stats.binomtest(b, b + c, 0.5).pvalue if b + c > 0 else 1.0
    return {"x_only": b, "y_only": c, "p": float(p)}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def load(tag: str) -> list[dict[str, Any]]:
    with (RESULTS_DIR / tag / "judged.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def trivial_baselines() -> dict[str, Any]:
    """T0 on the full MultiHop-RAG query set (no API calls)."""
    path = EVAL_DIR / "multihoprag_ordered.jsonl"
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    by_type: dict[str, Counter] = {}
    for r in rows:
        by_type.setdefault(r["stratum"], Counter())[r["answer"].strip().rstrip(".").lower()] += 1
    majority = {t: c.most_common(1)[0][0] for t, c in by_type.items()}
    # Constant hedge string from reports/literature-review.md (replicates its 85.6% claim).
    hedge = "yes no insufficient sam google"
    res = {}
    for name, fn in {"majority_per_type": lambda r: majority[r["stratum"]], "constant_hedge": lambda r: hedge}.items():
        res[name] = {
            "official_overlap": float(np.mean([official_overlap(fn(r), r["answer"]) for r in rows])),
            "exact_match": float(np.mean([exact_match(fn(r), r["answer"]) for r in rows])),
            "n": len(rows),
        }
    res["majority_answers"] = majority
    return res


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for cond in ordered({r["condition"] for r in rows}):
        rc = [r for r in rows if r["condition"] == cond]
        mhr = [r for r in rc if r["dataset"] == "MULTIHOPRAG"]
        swe = [r for r in rc if r["dataset"] == "SWEQA"]
        k = sum(r["judge_correct"] for r in mhr)
        swe_scores = np.array([r["sweqa_total"] for r in swe], dtype=float)
        rec = [r["evidence_recall"] for r in mhr if r.get("evidence_recall") is not None]
        out[cond] = {
            "n_mhr": len(mhr), "mhr_judge_acc": k / len(mhr) if mhr else None, "mhr_judge_ci": wilson(k, len(mhr)),
            "mhr_em_acc": float(np.mean([r["exact_match"] for r in mhr])) if mhr else None,
            "mhr_official_overlap": float(np.mean([r["official_overlap"] for r in mhr])) if mhr else None,
            "mhr_evidence_recall": float(np.mean(rec)) if rec else None,
            "n_swe": len(swe), "swe_mean": float(swe_scores.mean()) if len(swe) else None,
            "swe_ci": bootstrap_mean(swe_scores) if len(swe) else None,
            "cost_usd_total": round(sum(r["cost_usd"] for r in rc), 3),
            "cost_usd_per_q": round(float(np.mean([r["cost_usd"] for r in rc])), 4),
            "latency_s_median": float(np.median([r["duration_s"] or 0 for r in rc])),
            "tool_calls_mean": float(np.mean([r["num_tool_calls"] or 0 for r in rc])),
            "code_tool_calls_mean": float(np.mean([(r["tool_calls"] or {}).get("bash", 0)
                                                   + (r["tool_calls"] or {}).get("python_execute", 0) for r in rc])),
            "agents_spawned_mean": (float(np.mean([r["agents_spawned"] for r in rc if r.get("agents_spawned") is not None]))
                                    if any(r.get("agents_spawned") is not None for r in rc) else None),
            "errors": sum(1 for r in rc if r.get("error")),
            # Exploratory (post hoc): answer length and SWE-QA rubric dimensions.
            "resp_chars_median_mhr": float(np.median([len(r["response"]) for r in mhr])) if mhr else None,
            "resp_chars_median_swe": float(np.median([len(r["response"]) for r in swe])) if swe else None,
            "swe_dims": ({k: float(np.mean([r["sweqa_scores"].get(k, 0) for r in swe]))
                          for k in ("correctness", "completeness", "relevance", "clarity", "reasoning")} if swe else None),
            "no_tool_call_cases": sum(1 for r in rc if not r.get("tool_calls") or not any(
                (r["tool_calls"] or {}).get(t) for t in ("web_search", "web_fetch", "bash", "python_execute"))),
            "missing_final_answer": sum(1 for r in mhr if not r.get("final_answer")),
            "judge_em_agreement": float(np.mean([r["judge_correct"] == r["exact_match"] for r in mhr])) if mhr else None,
        }
    return out


def length_vs_score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Exploratory: Spearman correlation of SWE-QA answer length with rubric score."""
    sw = [r for r in rows if r["dataset"] == "SWEQA"]
    if len(sw) < 3:
        return {}
    rho = stats.spearmanr([len(r["response"]) for r in sw], [r["sweqa_total"] for r in sw])
    return {"n": len(sw), "spearman_rho": float(rho.statistic), "p": float(rho.pvalue)}


def paired_tests(rows: list[dict[str, Any]], a: str = "M", b: str = "B2") -> dict[str, Any]:
    by = {(r["condition"], r["id"]): r for r in rows}
    ids = sorted({r["id"] for r in rows if (a, r["id"]) in by and (b, r["id"]) in by})
    mhr = [i for i in ids if by[(a, i)]["dataset"] == "MULTIHOPRAG"]
    swe = [i for i in ids if by[(a, i)]["dataset"] == "SWEQA"]
    res: dict[str, Any] = {"n_paired_mhr": len(mhr), "n_paired_swe": len(swe)}
    if mhr:
        x = [bool(by[(a, i)]["judge_correct"]) for i in mhr]
        y = [bool(by[(b, i)]["judge_correct"]) for i in mhr]
        res["H1"] = {**mcnemar_exact(x, y), "diff": float(np.mean(x) - np.mean(y)),
                     "ci": bootstrap_diff(np.array(x, float), np.array(y, float))}
    if swe:
        x = np.array([by[(a, i)]["sweqa_total"] for i in swe], float)
        y = np.array([by[(b, i)]["sweqa_total"] for i in swe], float)
        p = float(stats.wilcoxon(x, y).pvalue) if np.any(x != y) else 1.0
        res["H3"] = {"p": p, "diff": float((x - y).mean()), "ci": bootstrap_diff(x, y)}
    ps = {h: res[h]["p"] for h in ("H1", "H3") if h in res}
    for h, padj in holm(ps).items():
        res[h]["p_holm"] = padj
        res[h]["supported"] = bool(padj < 0.05 and res[h]["ci"][0] > 0)
    return res


def _fmt_ci(ci: Any, pct: bool = True) -> str:
    if ci is None:
        return "–"
    lo, hi = ci
    return f"[{lo:.0%}, {hi:.0%}]" if pct else f"[{lo:.1f}, {hi:.1f}]"


def tables_md(summary: dict[str, Any], tests: dict[str, Any], t0: dict[str, Any]) -> str:
    lines = ["| Condition | max agents | agents spawned / q | MultiHop-RAG acc. (judge) [95% CI] | EM | official overlap | evidence recall | SWE-QA score /100 [95% CI] | $/question | median latency (s) | tool calls / q | bash+python / q | errors |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for cond, s in summary.items():
        lines.append(
            f"| {label(cond)} | {agent_cap(cond)} | {f"{s['agents_spawned_mean']:.1f}" if s['agents_spawned_mean'] is not None else '–'} | "
            f"{s['mhr_judge_acc']:.0%} {_fmt_ci(s['mhr_judge_ci'])} (n={s['n_mhr']}) | "
            f"{s['mhr_em_acc']:.0%} | {s['mhr_official_overlap']:.0%} | "
            f"{(s['mhr_evidence_recall'] or 0):.0%} | {s['swe_mean']:.1f} {_fmt_ci(s['swe_ci'], False)} (n={s['n_swe']}) | "
            f"{s['cost_usd_per_q']:.3f} | {s['latency_s_median']:.0f} | {s['tool_calls_mean']:.1f} | "
            f"{s['code_tool_calls_mean']:.1f} | {s['errors']} |")
    lines += ["", f"T0 trivial baselines on all {t0['majority_per_type']['n']} MultiHop-RAG queries (no API calls):", "",
              "| Trivial answer | official word-overlap metric | normalized EM |", "|---|---|---|"]
    for name in ("majority_per_type", "constant_hedge"):
        lines.append(f"| {name} | {t0[name]['official_overlap']:.1%} | {t0[name]['exact_match']:.1%} |")
    lines += ["", "Exploratory (post hoc): answer length and SWE-QA rubric dimensions (mean, 1-20 each):", "",
              "| Condition | median answer chars (MHR / SWE-QA) | correctness | completeness | relevance | clarity | reasoning | cases with no search/code tool call |",
              "|---|---|---|---|---|---|---|---|"]
    for cond, s in summary.items():
        d = s.get("swe_dims") or {}
        lines.append(f"| {label(cond)} | {s['resp_chars_median_mhr']:.0f} / {s['resp_chars_median_swe']:.0f} | "
                     + " | ".join(f"{d.get(k, float('nan')):.1f}" for k in ("correctness", "completeness", "relevance", "clarity", "reasoning"))
                     + f" | {s['no_tool_call_cases']} |")
    lines += ["", "Pre-registered paired tests (M vs B2, Holm across H1/H3):", "",
              "| Hypothesis | difference (M − B2) | 95% bootstrap CI | p | p (Holm) | supported |", "|---|---|---|---|---|---|"]
    for h, hname, pct in (("H1", "MultiHop-RAG accuracy", True), ("H3", "SWE-QA score", False)):
        if h in tests:
            t = tests[h]
            d = f"{t['diff']:+.0%}" if pct else f"{t['diff']:+.1f}"
            lines.append(f"| {h}: {hname} | {d} | {_fmt_ci(t['ci'], pct)} | {t['p']:.3f} | {t.get('p_holm', float('nan')):.3f} | {'yes' if t.get('supported') else 'no'} |")
    return "\n".join(lines) + "\n"


def figures(rows: list[dict[str, Any]], summary: dict[str, Any], out: Path) -> None:
    """Main bars (all arms), cost-vs-quality, agent-count sweep and per-question grid."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    conds = ordered(summary)
    color = {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(conds)}
    names = [label(c) for c in conds]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    # (a) MultiHop-RAG accuracy with Wilson CI (zero-based axis: no truncation)
    ax = axes[0]
    acc = [summary[c]["mhr_judge_acc"] for c in conds]
    err = [[a - summary[c]["mhr_judge_ci"][0] for a, c in zip(acc, conds)],
           [summary[c]["mhr_judge_ci"][1] - a for a, c in zip(acc, conds)]]
    ax.bar(names, acc, yerr=err, capsize=5, color=[color[c] for c in conds])
    ax.set_ylim(0, 1); ax.set_ylabel("accuracy (LLM judge)")
    ax.set_title(f"MultiHop-RAG (n={summary[conds[0]]['n_mhr']}/arm), 95% Wilson CI"); ax.tick_params(axis="x", rotation=30)
    # (b) SWE-QA score with bootstrap CI
    ax = axes[1]
    m = [summary[c]["swe_mean"] for c in conds]
    err = [[v - summary[c]["swe_ci"][0] for v, c in zip(m, conds)], [summary[c]["swe_ci"][1] - v for v, c in zip(m, conds)]]
    ax.bar(names, m, yerr=err, capsize=5, color=[color[c] for c in conds])
    ax.set_ylim(0, 100); ax.set_ylabel("SWE-QA rubric score /100")
    ax.set_title(f"SWE-QA (n={summary[conds[0]]['n_swe']}/arm), 95% bootstrap CI"); ax.tick_params(axis="x", rotation=30)
    # (c) cost per question vs quality
    ax = axes[2]
    for c in conds:
        ax.scatter(summary[c]["cost_usd_per_q"], summary[c]["mhr_judge_acc"], s=70, color=color[c], marker="o")
        ax.scatter(summary[c]["cost_usd_per_q"], summary[c]["swe_mean"] / 100, s=70, color=color[c], marker="s")
        ax.annotate(label(c), (summary[c]["cost_usd_per_q"], summary[c]["mhr_judge_acc"]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_xscale("symlog", linthresh=0.01); ax.set_ylim(0, 1)
    ax.set_xlabel("$ per question (API list price, symlog)"); ax.set_ylabel("quality: o = MHR acc., s = SWE-QA/100")
    ax.set_title("Cost vs quality")
    fig.tight_layout(); fig.savefig(out / "fig_main.png", dpi=150); plt.close(fig)

    # Agent-count sweep: quality and cost vs max agents (log2 x-axis).
    if len(conds) >= 3:
        caps = [agent_cap(c) for c in conds]
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        ax = axes[0]
        ax.errorbar(caps, acc, yerr=[[a - summary[c]["mhr_judge_ci"][0] for a, c in zip(acc, conds)],
                                     [summary[c]["mhr_judge_ci"][1] - a for a, c in zip(acc, conds)]],
                    marker="o", capsize=4, label="MultiHop-RAG accuracy")
        ax.errorbar(caps, [v / 100 for v in m], yerr=[[(v - summary[c]["swe_ci"][0]) / 100 for v, c in zip(m, conds)],
                                                      [(summary[c]["swe_ci"][1] - v) / 100 for v, c in zip(m, conds)]],
                    marker="s", capsize=4, label="SWE-QA score / 100")
        ax.set_xscale("log", base=2); ax.set_xticks(caps, [str(x) for x in caps]); ax.set_ylim(0, 1)
        ax.set_xlabel("max agents (1 = single agent B2; 16 = ArcticSwarm default M)"); ax.set_ylabel("quality")
        ax.legend(fontsize=8); ax.set_title("Quality vs number of agents (95% CIs)")
        ax = axes[1]
        ax.plot(caps, [summary[c]["cost_usd_per_q"] for c in conds], marker="o", label="$ / question")
        spawned = [summary[c]["agents_spawned_mean"] or (1 if c == "B2" else 0) for c in conds]
        ax2 = ax.twinx(); ax2.plot(caps, spawned, marker="^", color="grey", label="agents spawned / question")
        ax.set_xscale("log", base=2); ax.set_xticks(caps, [str(x) for x in caps]); ax.set_ylim(bottom=0); ax2.set_ylim(bottom=0)
        ax.set_xlabel("max agents"); ax.set_ylabel("$ per question"); ax2.set_ylabel("agents actually spawned")
        ax.set_title("Cost and agents used vs cap")
        fig.tight_layout(); fig.savefig(out / "fig_agent_sweep.png", dpi=150); plt.close(fig)

    # Per-question outcome grid (all questions, all arms) — no cherry-picking.
    ids = sorted({r["id"] for r in rows})
    by = {(r["condition"], r["id"]): r for r in rows}
    grid = np.full((len(conds), len(ids)), np.nan)
    for i, c in enumerate(conds):
        for j, q in enumerate(ids):
            r = by.get((c, q))
            if r:
                grid[i, j] = float(r["judge_correct"]) if r["dataset"] == "MULTIHOPRAG" else r["sweqa_total"] / 100
    fig, ax = plt.subplots(figsize=(max(8, len(ids) * 0.45), 0.6 + 0.45 * len(conds)))
    im = ax.imshow(grid, cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax.set_yticks(range(len(conds)), names); ax.set_xticks(range(len(ids)), ids, rotation=90, fontsize=7)
    fig.colorbar(im, ax=ax, label="correct (MHR) / score/100 (SWE-QA)")
    fig.tight_layout(); fig.savefig(out / "fig_per_question.png", dpi=150); plt.close(fig)


def analyze_tag(tag: str) -> dict[str, Any]:
    rows = load(tag)
    out = RESULTS_DIR / tag
    summary = summarize(rows)
    tests = paired_tests(rows) if {"M", "B2"} <= set(summary) else {}
    # Exploratory sweep (prereg Amendment 2): paired differences vs M, CIs only.
    sweep = {c: paired_tests(rows, a=c, b="M") for c in summary if c.startswith("M_cap") and "M" in summary}
    t0 = trivial_baselines()
    metrics = {"summary": summary, "tests": tests, "sweep_vs_M": sweep, "trivial_baselines": t0,
               "exploratory_length_vs_score": length_vs_score(rows)}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float), encoding="utf-8")
    (out / "tables.md").write_text(tables_md(summary, tests, t0), encoding="utf-8")
    if summary:
        figures(rows, summary, out)
    print((out / "tables.md").read_text(encoding="utf-8"))
    return metrics
