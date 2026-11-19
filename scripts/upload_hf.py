"""Upload evaluation artifacts to a public Hugging Face dataset inside a public collection.

Global context: no model is trained in this project, so the Hugging Face deliverable
is a dataset repo holding the question sample, judged outputs (all conditions), metrics,
figures and reports, grouped in one collection for this research line. Private on day 1;
made public on 2026-11-20 at the user's request, together with the GitHub repos.

Uses huggingface_hub's documented API: ``create_repo(private=False)``,
``upload_folder``, ``create_collection(private=False)`` and ``add_collection_item``
(https://huggingface.co/docs/huggingface_hub/guides/collections).
Usage: uv run python scripts/upload_hf.py
"""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "BurnyCoder/arcticswarm-folder-rag-results"
COLLECTION_TITLE = "ArcticSwarm folder RAG (Claude Haiku 5.5)"

CARD = """---
license: odc-by
pretty_name: ArcticSwarm folder-RAG evaluation outputs
tags: [rag, multi-agent, arcticswarm, evaluation]
---
# ArcticSwarm folder-RAG evaluation outputs

Judged outputs, metrics, figures and reports from adapting ArcticSwarm
(arXiv:2609.01870) to RAG over local folders with Claude Haiku 5.5. The code lives in
the GitHub repo https://github.com/BurnyCoder/arcticswarm-folder-rag-research (framework: https://github.com/BurnyCoder/ArcticSwarm-folder-rag); interactive explorer: https://burnycoder.github.io/arcticswarm-folder-rag-research/.

- `data_eval/`: seeded, stratified question samples. Sources: MultiHop-RAG
  (arXiv:2401.15391, ODC-By) and SWE-QA (arXiv:2509.14635, Apache-2.0).
- `results/<tag>/judged.jsonl`: one row per (condition, question), holding the full
  response, judge prompt and output, tokens, cost and tool counts.
- `results/<tag>/metrics.json`, `tables.md`, `fig_*.png`.
- `reports/`: preregistration, literature review, experiment reports and the paper.

Benchmark content keeps its original licenses (MultiHop-RAG: ODC-By; SWE-QA: Apache-2.0).
"""


def main() -> None:
    api = HfApi()
    api.create_repo(REPO_ID, repo_type="dataset", private=False, exist_ok=True)
    api.update_repo_settings(REPO_ID, repo_type="dataset", private=False)
    (ROOT / "results" / "README_hf.md").write_text(CARD, encoding="utf-8")
    api.upload_file(path_or_fileobj=str(ROOT / "results" / "README_hf.md"), path_in_repo="README.md",
                    repo_id=REPO_ID, repo_type="dataset")
    for sub in ("data_eval", "results", "reports"):
        api.upload_folder(folder_path=str(ROOT / sub), path_in_repo=sub, repo_id=REPO_ID, repo_type="dataset",
                          ignore_patterns=["README_hf.md"])
    existing = [c for c in api.list_collections(owner="BurnyCoder", limit=100) if c.title == COLLECTION_TITLE]
    coll = existing[0] if existing else api.create_collection(
        title=COLLECTION_TITLE, namespace="BurnyCoder", private=False,
        description="Adapting ArcticSwarm multi-agent research to RAG over local folders (Claude Haiku 5.5).")
    api.update_collection_metadata(coll.slug, private=False)  # also for a collection created private earlier
    try:
        api.add_collection_item(coll.slug, item_id=REPO_ID, item_type="dataset", exists_ok=True)
    except TypeError:  # older huggingface_hub without exists_ok
        api.add_collection_item(coll.slug, item_id=REPO_ID, item_type="dataset")
    print("dataset:", f"https://huggingface.co/datasets/{REPO_ID}", "| collection:", coll.slug)


if __name__ == "__main__":
    main()
