"""Upload evaluation artifacts to a PRIVATE Hugging Face dataset inside a PRIVATE collection.

Global context: no model is trained in this project, so the Hugging Face deliverable
is a dataset repo holding the question sample, judged outputs (all conditions), metrics,
figures and reports, grouped in one private collection for this research line. The user
asked that the GitHub repos and the HF collection stay private.

Uses huggingface_hub's documented API: ``create_repo(private=True)``,
``upload_folder``, ``create_collection(private=True)`` and ``add_collection_item``
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
# ArcticSwarm folder-RAG evaluation outputs (private)

Judged outputs, metrics, figures and reports from adapting ArcticSwarm
(arXiv:2609.01870) to RAG over local folders with Claude Haiku 5.5. The code lives in
the private GitHub repo `BurnyCoder/arcticswarm-folder-rag-research`.

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
    api.create_repo(REPO_ID, repo_type="dataset", private=True, exist_ok=True)
    (ROOT / "results" / "README_hf.md").write_text(CARD, encoding="utf-8")
    api.upload_file(path_or_fileobj=str(ROOT / "results" / "README_hf.md"), path_in_repo="README.md",
                    repo_id=REPO_ID, repo_type="dataset")
    for sub in ("data_eval", "results", "reports"):
        api.upload_folder(folder_path=str(ROOT / sub), path_in_repo=sub, repo_id=REPO_ID, repo_type="dataset",
                          ignore_patterns=["README_hf.md"])
    existing = [c for c in api.list_collections(owner="BurnyCoder", limit=100) if c.title == COLLECTION_TITLE]
    coll = existing[0] if existing else api.create_collection(
        title=COLLECTION_TITLE, namespace="BurnyCoder", private=True,
        description="Adapting ArcticSwarm multi-agent research to RAG over local folders (Claude Haiku 5.5).")
    try:
        api.add_collection_item(coll.slug, item_id=REPO_ID, item_type="dataset", exists_ok=True)
    except TypeError:  # older huggingface_hub without exists_ok
        api.add_collection_item(coll.slug, item_id=REPO_ID, item_type="dataset")
    print("dataset:", f"https://huggingface.co/datasets/{REPO_ID}", "| collection:", coll.slug)


if __name__ == "__main__":
    main()
