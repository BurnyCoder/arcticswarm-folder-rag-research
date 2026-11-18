"""Draw the system architecture figure (reports/figures/architecture.png).

Global context: the paper and README need an AI-paper-style architecture diagram.
It is drawn with plain matplotlib patches (no external renderer needed) so it can be
regenerated anywhere: ``uv run python scripts/make_architecture_figure.py``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports" / "figures" / "architecture.png"


def box(ax, x, y, w, h, text, fc, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02", fc=fc, ec="#333", lw=1))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, x1, y1, x2, y2, text="", style="-|>", color="#333", ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=color, lw=1.1, ls=ls))
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.012, text, fontsize=7, ha="center", color=color)


def main() -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    box(ax, 0.01, 0.80, 0.16, 0.12, "Question\n+ 'FINAL ANSWER:'\nformat line", "#f2f2f2")
    box(ax, 0.22, 0.78, 0.18, 0.16, "Orchestrator\n(Haiku 5.5, effort high)\ncreate_task / wait /\nprepare_report", "#cfe2ff")
    box(ax, 0.47, 0.87, 0.22, 0.07, "Subagent A (browsing)\nisolated: post-only", "#d9f2d9")
    box(ax, 0.47, 0.74, 0.22, 0.07, "Subagent B (browsing)\nisolated: post-only", "#d9f2d9")
    box(ax, 0.47, 0.55, 0.22, 0.12, "Reviewers / auditor\n(dedicated + builder)\nChallenge / Alternative /\nVerified", "#ffe8cc")
    box(ax, 0.22, 0.47, 0.18, 0.20, "Gated bulletin board (BBS)\n#discoveries\n#key-findings\n#discussion", "#fff3b0")
    box(ax, 0.75, 0.80, 0.24, 0.14, "web_search: BM25 (bm25s)\nover line-aligned chunks\n-> corpus://folder/path#La-b", "#e8e0ff")
    box(ax, 0.75, 0.64, 0.24, 0.12, "web_fetch: read file /\nline span by path (paged)", "#e8e0ff")
    box(ax, 0.75, 0.40, 0.24, 0.20, "bash + python_execute\nWSL2 Ubuntu sandbox (root)\nno Windows drives, no interop,\nno API keys; apt/pip install;\nsoft proxy guard", "#ffd6e0")
    box(ax, 0.75, 0.14, 0.24, 0.18, "Local folder\n(canonical copy on D:)\n+ hash-verified copy\nin /corpus/<run>/<folder>", "#e6e6e6")
    box(ax, 0.22, 0.16, 0.18, 0.18, "Report with file citations\n+ FINAL ANSWER line", "#cfe2ff")
    box(ax, 0.01, 0.16, 0.16, 0.18, "Unified judge (Haiku 5.5)\nMHR: strict binary\nSWE-QA: 5-dim rubric\n+ EM, cost, recall", "#f2f2f2")
    arrow(ax, 0.17, 0.86, 0.22, 0.86)
    arrow(ax, 0.40, 0.90, 0.47, 0.90, "isolated=true")
    arrow(ax, 0.40, 0.83, 0.47, 0.775)
    arrow(ax, 0.40, 0.80, 0.47, 0.63)
    arrow(ax, 0.47, 0.88, 0.38, 0.67, color="#2b8a3e")
    arrow(ax, 0.47, 0.75, 0.40, 0.63, color="#2b8a3e")
    arrow(ax, 0.47, 0.59, 0.40, 0.55, style="<|-|>", color="#c2410c")
    arrow(ax, 0.31, 0.67, 0.31, 0.78, color="#1d4ed8")
    for y in (0.905, 0.775):
        arrow(ax, 0.69, y, 0.75, 0.87 if y > 0.8 else 0.70, color="#6d28d9")
        arrow(ax, 0.69, y - 0.02, 0.75, 0.50, color="#be185d", ls="--")
    ax.text(0.45, 0.36, "green: post-only (isolation)   orange: read+write (review)\nblue: orchestrator reads the BBS   purple: folder tools\npink dashed: sandboxed code execution", fontsize=7.5, color="#333")
    arrow(ax, 0.87, 0.80, 0.87, 0.76, color="#6d28d9")
    arrow(ax, 0.87, 0.64, 0.87, 0.60, color="#6d28d9")
    arrow(ax, 0.87, 0.40, 0.87, 0.32, color="#555")
    arrow(ax, 0.31, 0.47, 0.31, 0.34, "prepare_report\n(verifier gate)")
    arrow(ax, 0.22, 0.25, 0.17, 0.25)
    ax.set_title("ArcticSwarm adapted to RAG over a local folder (all agents: Claude Haiku 5.5)", fontsize=11)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, bbox_inches="tight")
    print(OUT)


if __name__ == "__main__":
    main()
