"""Run ArcticSwarm conditions (M = gated-BBS swarm, B2 = single agent) per folder.

Global context: ``arcticswarm-eval`` evaluates one corpus per invocation
(``web.corpus_local_path``), so each condition is run once per folder (MultiHop-RAG,
then each SWE-QA repository). Before every invocation the folder is re-synced into
the WSL sandbox and hash-verified, so agent writes never leak between runs; after it,
the sandbox copy is verified again and the result recorded (integrity check).

Every run gets: a timestamped console log (tee'd to the terminal), a full LLM-call
JSONL log (``ARCTICSWARM_LLM_LOG``: every prompt delta and every output), and the
ArcticSwarm output dir (report.json, per-case trajectories).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from folderrag import sandbox
from folderrag.datasets import write_arcticswarm_csv
from folderrag.settings import (
    EVAL_DIR, FOLDERS_DIR, INDEX_DIR, LOGS_DIR, REPO, RUNS_DIR,
    SANDBOX_CORPUS_ROOT, SANDBOX_NO_PROXY, SANDBOX_PROXY,
)

log = logging.getLogger(__name__)
ARCTIC = REPO / "ArcticSwarm"
CONFIGS = {
    "M": [ARCTIC / "conf/bench/folder_rag.yaml"],
    "B2": [ARCTIC / "conf/bench/folder_rag.yaml", ARCTIC / "conf/bench/folder_rag_single_agent.yaml"],
}


def load_sample(path: Path = EVAL_DIR / "day1_sample.jsonl") -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def run_folder(condition: str, folder: str, rows: list[dict], tag: str, extra: list[str] | None = None) -> Path:
    """Run one condition on one folder's rows; returns the ArcticSwarm output dir."""
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = folder.replace("/", "__")
    out_dir = RUNS_DIR / tag / condition / name
    csv_path = RUNS_DIR / tag / condition / f"{name}.csv"
    write_arcticswarm_csv(rows, csv_path, rows[0]["dataset"])
    src = FOLDERS_DIR / folder
    dest = f"{SANDBOX_CORPUS_ROOT}/{folder}"
    sandbox.sync_corpus(src, dest)  # fresh, hash-verified copy for this run

    cmd = [str(REPO / ".venv/Scripts/arcticswarm-eval")]
    for c in CONFIGS[condition]:
        cmd += ["-c", str(c)]
    cmd += [
        f"web.corpus_local_path={src}",
        f"web.folder_index_dir={INDEX_DIR}",
        f"tools.exec_corpus_root={dest}",
        f"tools.exec_proxy={SANDBOX_PROXY}",
        f"tools.exec_no_proxy={SANDBOX_NO_PROXY}",
        f"eval.csv_path={csv_path}",
        f"eval.datasets=[{rows[0]['dataset']}]",
        f"eval.output={out_dir}",
        # All conditions are re-judged uniformly by folderrag.judge, so skip
        # ArcticSwarm's QA judge (its cheap answer-only judge still runs).
        "eval.qa_llm=false",
        *(extra or []),
    ]
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               ARCTICSWARM_LLM_LOG=str(LOGS_DIR / f"llm_calls_{tag}_{condition}_{name}_{ts}.jsonl"))
    console = LOGS_DIR / f"run_{tag}_{condition}_{name}_{ts}.log"
    log.info("running %s on %s (%d questions) -> %s", condition, folder, len(rows), out_dir)
    with console.open("w", encoding="utf-8") as fh:
        fh.write(" ".join(cmd) + "\n")
        proc = subprocess.Popen(cmd, cwd=str(ARCTIC), env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:  # tee: terminal + timestamped file, never truncated
            sys.stdout.write(line)
            fh.write(f"{dt.datetime.now():%H:%M:%S} {line}")
            fh.flush()
        rc = proc.wait()
    try:
        sandbox.verify_corpus(src, dest)
        integrity = "unchanged"
    except RuntimeError as exc:  # agents modified the sandbox copy; re-synced before the next run anyway
        integrity = str(exc)
    (out_dir / "harness_meta.json").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "harness_meta.json").write_text(json.dumps({
        "condition": condition, "folder": folder, "ids": [r["id"] for r in rows], "returncode": rc,
        "started": ts, "finished": dt.datetime.now().strftime("%Y%m%d_%H%M%S"),
        "console_log": str(console), "llm_log": env["ARCTICSWARM_LLM_LOG"],
        "sandbox_corpus_after_run": integrity, "cmd": cmd,
    }, indent=2), encoding="utf-8")
    log.info("%s on %s finished rc=%d integrity=%s", condition, folder, rc, integrity)
    return out_dir


def run_condition(condition: str, tag: str = "day1", limit_per_folder: int | None = None,
                  folders: list[str] | None = None, extra: list[str] | None = None) -> list[Path]:
    """Run a condition over all folders of the sample (optionally the first k rows each)."""
    sample = load_sample()
    outs = []
    for folder in folders or list(dict.fromkeys(r["folder"] for r in sample)):
        rows = [r for r in sample if r["folder"] == folder][: limit_per_folder or None]
        if rows:
            outs.append(run_folder(condition, folder, rows, tag, extra))
    return outs
