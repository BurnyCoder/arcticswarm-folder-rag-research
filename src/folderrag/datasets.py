"""Materialise benchmark corpora as folders of files and sample the question sets.

Global context: the experiment asks agents to answer questions from a local folder.
This module turns two public benchmarks into such folders and writes, for the
pre-registered sample, (a) a JSONL question file used by the harness/judge and
(b) ArcticSwarm's unified eval CSV (one per folder) consumed by ``arcticswarm-eval``.

* MultiHop-RAG (Tang & Yang 2024, arXiv:2401.15391; HF ``yixuantt/MultiHopRAG``,
  ODC-By): the 609 news articles become ``<source>/<YYYY-MM-DD>_<slug>.md`` files
  with a metadata header (questions refer to source names and dates).
* SWE-QA v2 (Peng et al. 2026, arXiv:2509.14635; HF ``swe-qa/SWE-QA-Benchmark``,
  Apache-2.0): each repository is cloned at the commit pinned in the benchmark's
  ``repo_commit.txt`` (GitHub peng-weihan/SWE-QA-Bench).

Sampling (preregistration Amendment 1): a seeded *stratified ordering* — within each
stratum items are shuffled and given systematic-sampling keys ``(i + u) / n_stratum``;
sorting by key interleaves strata so the first k items allocate the strata
(near-)proportionally. Exact per-stratum quotas for the day-1 sample are enforced
with the largest-remainder method.
"""

from __future__ import annotations

import json
import logging
import random
import re
import subprocess
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download  # downloads the auto-converted parquet files

from folderrag.settings import EVAL_DIR, FOLDERS_DIR

log = logging.getLogger(__name__)
SEED = 20261118

# Answer-format instructions appended to every question (preregistration §5).
FORMAT_GENERIC = "\n\nFinish your response with a final line of the form `FINAL ANSWER: <answer>`."
FORMAT_MHR = (
    "\n\nAnswer using only the files in the folder. Finish your response with a final line of the form "
    "`FINAL ANSWER: <answer>`, where <answer> is as short as possible: yes/no, an entity name, "
    "before/after, or 'Insufficient information' if the folder does not contain the answer."
)

# SWE-QA repositories used (subset of the 15) and their pinned commits
# (from https://github.com/peng-weihan/SWE-QA-Bench/blob/main/repo_commit.txt).
SWEQA_REPOS = {
    "requests": ("https://github.com/psf/requests", "46e939b"),
    "flask": ("https://github.com/pallets/flask", "85c5d93"),
    "pytest": ("https://github.com/pytest-dev/pytest", "5989efe"),
    "django": ("https://github.com/django/django", "14fc2e9"),
}


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:max_len].rstrip("-") or "untitled"


def largest_remainder(counts: dict[str, int], n: int) -> dict[str, int]:
    """Allocate ``n`` items to strata proportionally to ``counts`` (Hamilton method)."""
    total = sum(counts.values())
    raw = {k: n * c / total for k, c in counts.items()}
    quota = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - quota[k], reverse=True)[: n - sum(quota.values())]:
        quota[k] += 1
    return quota


def stratified_order(items: list[dict], key: str, seed: int = SEED) -> list[dict]:
    """Seeded stratified ordering (systematic-sampling keys within each stratum)."""
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it[key], []).append(it)
    keyed = []
    for g in sorted(groups):
        lst = groups[g][:]
        rng.shuffle(lst)
        u = rng.random()
        keyed += [((i + u) / len(lst), it) for i, it in enumerate(lst)]
    return [it for _, it in sorted(keyed, key=lambda x: x[0])]


def take_quota(ordered: list[dict], key: str, quota: dict[str, int]) -> list[dict]:
    """First items of the stratified ordering until every stratum's quota is met."""
    left = dict(quota)
    out = []
    for it in ordered:
        if left.get(it[key], 0) > 0:
            out.append(it)
            left[it[key]] -= 1
    return out


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_arcticswarm_csv(rows: list[dict], path: Path, dataset: str) -> None:
    """Unified eval CSV via ArcticSwarm's own writer (eval/data/external/utils.py)."""
    from arcticswarm.eval.data.external.utils import write_unified_eval_csv
    write_unified_eval_csv(
        [{"id": r["id"], "question": r["prompt"], "expected_answer": r["answer"]} for r in rows],
        path, dataset_name=dataset, reference_tools=["web_search"],
    )


# ---------------------------------------------------------------------------
# MultiHop-RAG
# ---------------------------------------------------------------------------


def _hf_parquet(repo: str, config: str, split: str) -> pd.DataFrame:
    p = hf_hub_download(repo, f"{config}/{split}/0000.parquet", repo_type="dataset", revision="refs/convert/parquet")
    return pd.read_parquet(p)


def prepare_multihoprag(n_by_type: dict[str, int] | None = None) -> list[dict]:
    """Write the 609-article folder and the sampled questions; return the sample."""
    corpus = _hf_parquet("yixuantt/MultiHopRAG", "corpus", "train")
    queries = _hf_parquet("yixuantt/MultiHopRAG", "MultiHopRAG", "train")
    root = FOLDERS_DIR / "multihoprag"
    url_to_path: dict[str, str] = {}
    used: set[str] = set()
    for row in corpus.itertuples(index=False):
        date = str(row.published_at or "")[:10] or "undated"
        rel = f"{slugify(row.source or 'unknown', 30)}/{date}_{slugify(row.title or 'untitled')}.md"
        while rel in used:  # disambiguate identical titles on the same day
            rel = rel[:-3] + "_2.md"
        used.add(rel)
        url_to_path[str(row.url)] = rel
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# {row.title}\n\nSource: {row.source}\nAuthor: {row.author}\n"
            f"Published: {row.published_at}\nCategory: {row.category}\nURL: {row.url}\n\n"
        )
        p.write_text(header + str(row.body), encoding="utf-8", newline="\n")
    log.info("MultiHop-RAG folder: %d files at %s", len(used), root)

    items = []
    for i, row in enumerate(queries.itertuples(index=False)):
        gold_files = sorted({url_to_path.get(str(e["url"]), "") for e in row.evidence_list} - {""})
        items.append({
            "id": f"mhr_{i:04d}", "dataset": "MULTIHOPRAG", "folder": "multihoprag",
            "stratum": row.question_type, "question": row.query, "prompt": row.query + FORMAT_MHR,
            "answer": row.answer, "gold_files": gold_files,
        })
    ordered = stratified_order(items, "stratum")
    write_jsonl(ordered, EVAL_DIR / "multihoprag_ordered.jsonl")  # full seeded ordering (for later days)
    counts = {k: sum(1 for it in items if it["stratum"] == k) for k in sorted({it["stratum"] for it in items})}
    quota = n_by_type or largest_remainder(counts, 10)
    sample = take_quota(ordered, "stratum", quota)
    log.info("MultiHop-RAG strata %s -> quota %s", counts, quota)
    return sample


# ---------------------------------------------------------------------------
# SWE-QA
# ---------------------------------------------------------------------------


def clone_repo(name: str) -> Path:
    """Clone a SWE-QA repository at its pinned commit (blobless clone, idempotent)."""
    url, commit = SWEQA_REPOS[name]
    dest = FOLDERS_DIR / "sweqa" / name
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--filter=blob:none", "--no-checkout", url, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "-c", "advice.detachedHead=false", "checkout", "-f", commit], check=True)
    subprocess.run(["git", "-C", str(dest), "clean", "-fdx", "-q"], check=True)
    return dest


def prepare_sweqa(n_by_repo: dict[str, int] | None = None) -> list[dict]:
    """Clone the repos and sample questions (equal-ish per repo); return the sample."""
    quota = n_by_repo or {"requests": 3, "flask": 3, "pytest": 2, "django": 2}
    items = []
    for repo in SWEQA_REPOS:
        clone_repo(repo)
        df = _hf_parquet("swe-qa/SWE-QA-Benchmark", "default", repo)
        for i, row in enumerate(df.itertuples(index=False)):
            items.append({
                "id": f"sweqa_{repo}_{i:02d}", "dataset": "SWEQA", "folder": f"sweqa/{repo}",
                "stratum": repo, "question": row.question, "prompt": row.question + FORMAT_GENERIC,
                "answer": row.answer, "gold_files": [],
            })
    ordered = stratified_order(items, "stratum")
    write_jsonl(ordered, EVAL_DIR / "sweqa_ordered.jsonl")
    return take_quota(ordered, "stratum", quota)


def prepare_all() -> list[dict]:
    """Build both folders and write the day-1 sample (JSONL + per-folder CSVs)."""
    sample = prepare_multihoprag() + prepare_sweqa()
    write_jsonl(sample, EVAL_DIR / "day1_sample.jsonl")
    for folder in sorted({r["folder"] for r in sample}):
        rows = [r for r in sample if r["folder"] == folder]
        write_arcticswarm_csv(rows, EVAL_DIR / "csv" / f"{folder.replace('/', '__')}.csv", rows[0]["dataset"])
    log.info("day-1 sample: %d questions", len(sample))
    return sample
