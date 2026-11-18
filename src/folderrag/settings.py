"""Project-wide paths and constants, read from the project ``.env``.

Global context: every phase of the harness (dataset preparation, sandbox sync,
ArcticSwarm runs, judging, analysis) imports its paths from here so that the large
data (corpora, indexes, raw runs) lives on D: (C: has little free space) while the
small, committed results live in the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv  # python-dotenv: reads KEY=VALUE lines from .env

# Repository root = two levels above this file (src/folderrag/settings.py).
REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO / ".env")  # makes ANTHROPIC_API_KEY / ANTHROPIC_WORKSPACE_ID visible

# Large, regenerable artefacts (git-ignored, outside the repo).
DATA_DIR = Path(os.environ.get("FOLDERRAG_DATA_DIR", r"D:\AI\arcticswarm-folder-rag"))
FOLDERS_DIR = DATA_DIR / "folders"       # materialised corpora (one dir per folder)
INDEX_DIR = DATA_DIR / "index"           # persisted BM25 indexes
RUNS_DIR = DATA_DIR / "runs"             # raw ArcticSwarm eval outputs (trajectories)
LOGS_DIR = DATA_DIR / "logs"             # full LLM call logs (prompts + outputs)

# Small, committed artefacts.
CONF_DIR = REPO / "conf"                 # ArcticSwarm run configs for folder RAG
EVAL_DIR = REPO / "data_eval"            # sampled question sets (CSV/JSONL, committed)
RESULTS_DIR = REPO / "results"           # judged answers, metrics, tables, figures

# Models (claude-api skill model table: "haiku" with no version -> claude-haiku-5-5).
MODEL = os.environ.get("FOLDERRAG_MODEL", "claude-haiku-5-5")
JUDGE_MODEL = os.environ.get("FOLDERRAG_JUDGE_MODEL", "claude-haiku-5-5")

# Pricing per million tokens for prompts <= 100K tokens (Anthropic first-party
# rates via the claude-api skill model table, cached 2026-11-03). Cache reads are
# 0.1x input; 5-minute cache writes 1.25x input.
PRICE = {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125}
PRICE_LONG = {"input": 0.50, "output": 2.50, "cache_read": 0.05, "cache_write": 0.625}  # >100K-token prompts

# WSL sandbox for agent code execution (see ArcticSwarm/arcticswarm/tools/sandbox_exec.py).
SANDBOX_DISTRO = os.environ.get("FOLDERRAG_SANDBOX_DISTRO", "arcticswarm-sandbox")
SANDBOX_CORPUS_ROOT = "/corpus"          # corpora are copied to /corpus/<dataset>/<folder>
# Soft no-web guard: proxy everything to a dead port except package hosts.
SANDBOX_PROXY = "http://127.0.0.1:9"
SANDBOX_NO_PROXY = ",".join([
    "localhost", "127.0.0.1",
    "archive.ubuntu.com", "security.ubuntu.com", "ports.ubuntu.com",
    "pypi.org", "files.pythonhosted.org", "astral.sh", "github.com",
    "objects.githubusercontent.com", "release-assets.githubusercontent.com",
])

for _d in (FOLDERS_DIR, INDEX_DIR, RUNS_DIR, LOGS_DIR, EVAL_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
