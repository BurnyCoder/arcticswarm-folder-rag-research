---
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
