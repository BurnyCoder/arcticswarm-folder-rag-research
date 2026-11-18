"""Render the paper and the README results block from results files (no hand-typed numbers).

Global context: CLAUDE.md requires every reported number to come from a script that
reads result files. The paper is written as ``reports/paper/paper_template.md`` with
placeholders; this script fills them from ``results/<tag>/metrics.json`` and
``results/<tag>/tables.md`` and renders ``reports/paper/paper.pdf`` with pandoc.

Placeholder syntax:
  {{summary.M.mhr_judge_acc|pct}}      -> value at that path in metrics.json, formatted
  {{tests.H1.ci|pctci}}                -> "[a%, b%]"
  {{TABLES}}                           -> contents of results/<tag>/tables.md
Formats: pct (0 decimals %), pct1, f1, f2, f3, usd (3 decimals), int, pctci, f1ci, raw.

Usage: uv run python scripts/build_paper.py --tag day1
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PH = re.compile(r"\{\{([A-Za-z0-9_.\-]+)(?:\|([a-z0-9]+))?\}\}")


def lookup(obj, path: str):
    for part in path.split("."):
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def fmt(v, kind: str | None) -> str:
    if v is None:
        return "n/a"
    k = kind or "raw"
    if k == "pct":
        return f"{v:.0%}"
    if k == "pct1":
        return f"{v:.1%}"
    if k in ("f1", "f2", "f3"):
        return f"{v:.{k[1]}f}"
    if k == "usd":
        return f"${v:.3f}"
    if k == "int":
        return f"{int(round(v))}"
    if k == "pctci":
        return f"[{v[0]:.0%}, {v[1]:.0%}]"
    if k == "f1ci":
        return f"[{v[0]:.1f}, {v[1]:.1f}]"
    return str(v)


def fill(text: str, metrics: dict, tables: str) -> str:
    text = text.replace("{{TABLES}}", tables)
    return PH.sub(lambda m: fmt(lookup(metrics, m.group(1)), m.group(2)), text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="day1")
    a = ap.parse_args()
    res = ROOT / "results" / a.tag
    metrics = json.loads((res / "metrics.json").read_text(encoding="utf-8"))
    tables = (res / "tables.md").read_text(encoding="utf-8")

    # 1) Every report template (reports/**/<name>_template.md -> <name>.md), incl. the paper.
    for tmpl_path in sorted((ROOT / "reports").rglob("*_template.md")):
        if tmpl_path.name == "readme_results_template.md":
            continue
        target = tmpl_path.with_name(tmpl_path.name.replace("_template.md", ".md"))
        target.write_text(fill(tmpl_path.read_text(encoding="utf-8"), metrics, tables), encoding="utf-8")
        print("filled", target.relative_to(ROOT))
    out_md = ROOT / "reports/paper/paper.md"
    pandoc = shutil.which("pandoc")
    if pandoc:
        cmd = [pandoc, str(out_md), "-o", str(ROOT / "reports/paper/paper.pdf"), "--pdf-engine=xelatex",
               "-V", "geometry:margin=2cm", "-V", "mainfont=Cambria", "-V", "monofont=Consolas",
               "--resource-path", str(ROOT / "reports/paper")]
        r = subprocess.run(cmd, capture_output=True, text=True)
        print("pandoc:", r.returncode, r.stderr[-2000:])

    # 2) README results block (between markers)
    readme = ROOT / "README.md"
    block_t = ROOT / "reports/paper/readme_results_template.md"
    if block_t.exists():
        block = fill(block_t.read_text(encoding="utf-8"), metrics, tables)
        txt = readme.read_text(encoding="utf-8")
        start, end = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
        if start in txt and end in txt:
            txt = txt[: txt.index(start) + len(start)] + "\n" + block + "\n" + txt[txt.index(end):]
            readme.write_text(txt, encoding="utf-8")
    print("wrote", out_md)


if __name__ == "__main__":
    main()
