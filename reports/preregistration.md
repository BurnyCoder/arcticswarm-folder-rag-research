# Preregistration: ArcticSwarm (gated-BBS multi-agent research) for RAG over local folders, all agents on Claude Haiku 5.5

- **Author:** Libor "Burny" Burian
- **Date registered:** 2026-11-18. Written and committed before any evaluation question was run; only API-shape probes (`scripts/probe_haiku.py`) existed at that point.
- **Status:** v1.1. It incorporates the design changes forced by the literature review ([literature-review.md](literature-review.md)), all made before any results existed.

## 1. Question
Does ArcticSwarm's gated-bulletin-board multi-agent orchestration ([Yoon et al. 2026, arXiv:2609.01870](https://arxiv.org/abs/2609.01870)) improve answer quality over a single agent? The comparison holds the model, tools and harness fixed. The setting is retrieval-augmented generation over a **local folder of many files**, with no web access, all agents run on `claude-haiku-5-5`, and agents may run arbitrary bash/Python over the files.

## 2. System under test
ArcticSwarm (fork, branch `folder-rag`) is adapted as follows:
- **New `folder` corpus backend.** BM25 over line-aligned chunks of every file, via [bm25s](https://github.com/xhluca/bm25s) ([Lù 2024](https://arxiv.org/abs/2407.03618)). It is exposed through the existing `web_search` / `web_fetch` tool slots. `web_fetch` reads a file or line span by path, and citations take the form `corpus://folder/<path>#L<a>-<b>`.
- **`bash` and `python_execute`** run as root inside an isolated WSL2 Ubuntu distro:
  - no Windows drive mounts, no interop, no API keys in the environment
  - agents can apt/pip-install any tool
  - a soft proxy guard allows only package hosts
- **All roles run on `claude-haiku-5-5`:** orchestrator, subagents, auditor/reviewers and judge. It uses adaptive thinking with `output_config.effort`. Orchestrator effort is `high`; subagent and auditor effort is `medium`.

## 3. Datasets and samples
1. **MultiHop-RAG** ([Tang & Yang 2024](https://arxiv.org/abs/2401.15391); [HF](https://huggingface.co/datasets/yixuantt/MultiHopRAG), ODC-By).
   - The 609 articles are written as 609 `.md` files (with a metadata header) in `<source>/` subfolders.
   - The sample is stratified proportionally by `question_type` over inference, comparison, temporal and null queries. Seed: `20261118`.
2. **SWE-QA v2** ([Peng et al. 2026](https://arxiv.org/abs/2509.14635); [HF](https://huggingface.co/datasets/swe-qa/SWE-QA-Benchmark), Apache-2.0).
   - Repositories: `requests`, `flask`, `pytest`, `django`, at the commits pinned in `repo_commit.txt`.
   - The sample takes an equal number of questions per repository. Seed: `20261118`.

**Sample size (budget rule, fixed now).**
- The target is N=150 for MultiHop-RAG and N=60 for SWE-QA.
- A smoke test of ≤3 questions per dataset measures $/question for M and B2.
- If the projected cost of M+B2 exceeds the **$50 daily budget**, N is scaled down proportionally on both datasets. The stratification and the seed stay the same, and samples are taken as the first-k rows of the seeded stratified ordering.
- The final N is recorded in `reports/plan.md` before the main run starts.
- Every condition uses exactly the same question ids, so all comparisons are paired.

## 4. Conditions

| Id | Condition | When |
|---|---|---|
| **M** | ArcticSwarm gated-BBS swarm (paper defaults for gates; Haiku-specific limits in `conf/folder_rag.yaml`), tools = BM25 search + file fetch + sandboxed bash + python | Day 1 (first) |
| **B2** | ArcticSwarm single agent (`swarm.enabled=false`), same tools, model and effort | Day 1 (second) |
| T0 | Trivial MultiHop-RAG answers: majority answer per question type, plus a constant hedge string. No API calls | Day 1 (analysis only) |
| B1 | BM25 top-10 one-shot RAG | later day |
| C1 | Closed-book (no retrieval): a memorization/contamination control | later day |
| C2 | Random-chunk RAG (k=10): checks that retrieval matters | later day |
| O | Gold-evidence oracle (MultiHop-RAG only; SWE-QA has no gold evidence) | later day |
| B3 | Compute-matched majority vote over independent single agents (the paper's 62.5% baseline) | later day |
| A1 | Ablation: M without bash/python | later day |

The user constrained the run order: main method first, then baselines, then ablations. On day 1 only M and one baseline (B2) are run once.

## 5. Answer format and metrics
- Every question is suffixed with: *"Finish your response with a final line of the form `FINAL ANSWER: <answer>`."* For MultiHop-RAG it adds: *"…where <answer> is as short as possible: yes/no, an entity name, before/after, or 'Insufficient information' if the folder does not contain the answer."*
- **MultiHop-RAG primary metric: `judge_correct`.**
  - Claude Haiku 5.5 is given the question, the gold answer and *only* the extracted FINAL ANSWER line.
  - It returns a strict binary equivalence verdict with JSON structured output.
  - A missing FINAL ANSWER line counts as incorrect.
- **MultiHop-RAG secondary metrics:**
  - normalized exact match of the FINAL ANSWER (lowercase, strip punctuation and articles; yes/no prefix match)
  - the official word-overlap metric, reported only to show it is inflated (it is gameable: see the literature review)
- **SWE-QA primary metric:** the SWE-QA 5-dimension rubric (correctness, completeness, relevance, clarity, reasoning; 1–20 each, total 0–100).
  - The rubric prompt is copied from `Benchmark construction/score/llm-as-a-judge.py` (Apache-2.0).
  - The judge is Haiku 5.5, not the paper's model (deviation).
  - The full response is judged.
- **Exploratory metrics** (not hypothesis tests):
  - cost per question from API token usage × list price
  - wall-clock latency
  - number of tool calls, and bash/python usage
  - MultiHop-RAG gold-evidence recall: the fraction of gold evidence files whose path appears in any tool output or call of the trajectory
  - per-question-type and per-repository breakdowns

## 6. Hypotheses and analysis plan
- **H1 (primary):** M > B2 on MultiHop-RAG `judge_correct`.
  - Test: exact two-sided McNemar test on the paired outcomes.
  - Report: Wilson 95% CIs per condition and a paired-bootstrap 95% CI of the difference (10,000 resamples, seed 0).
- **H3 (primary):** M > B2 on SWE-QA total score.
  - Test: two-sided Wilcoxon signed-rank test.
  - Report: a paired-bootstrap 95% CI of the mean difference.
- **Multiple comparisons:** Holm correction across {H1, H3} for day 1. Later days add H2 (M > B1), H4 (M > A1) and H5 (M > B3), each with Holm over the full family.
- **Falsification:** a hypothesis is *not supported* if the Holm-adjusted p ≥ 0.05 **or** the bootstrap CI of the difference includes 0. A significant difference in the opposite direction is reported as a negative result.
- **Judge-validity checks:**
  - On MultiHop-RAG, agreement between `judge_correct` and normalized exact match, plus manual inspection of up to 20 disagreements.
  - Judge-family bias, i.e. a Claude judge scoring Claude answers ([Panickssery et al. 2024](https://arxiv.org/abs/2404.13076)), applies equally to M and B2, so it is not expected to bias the paired M-vs-B2 contrast. It does limit comparisons with published numbers.
- **Run-to-run variance:** the API exposes no seed. A repeat of M and B2 on a subset is planned for a later day; day-1 results come from a single run, which is stated as a limitation.
- **Failures:** errors and timeouts are scored as incorrect (0 for SWE-QA), and their counts are reported per condition. There are no reruns of individual failed questions unless the cause is an infrastructure bug, which would be documented; in that case the whole condition is re-run.

## 7. What would change our mind
- If M ≤ B2 on both datasets, then on this setup the gated swarm's gains do not transfer to Haiku-scale models on local-folder RAG.
- If M > B2 on MultiHop-RAG but not on SWE-QA, the benefit is specific to multi-document fact aggregation rather than code understanding. The reverse would indicate the opposite.

## 8. Known threats
- **Contamination:** the 2023 news and popular repositories predate Haiku 5.5's training data. The closed-book control C1 will quantify this on a later day.
- **Single seed, small N.**
- **Same-family judge.**
- **Different settings from the paper:** BM25 instead of dense retrieval; lower budgets than the paper.
- **Soft network guard only.**
- **Unmatched compute:** M uses more compute than B2. Cost is therefore reported, and B3 (compute-matched voting) is scheduled.

## Amendment 1 (2026-11-18, before any evaluation question was run)
The user set the sample to **20 questions per condition**:
- **10 MultiHop-RAG questions**, using the proportional largest-remainder allocation over question types: inference 3, comparison 4, temporal 2, null 1.
- **10 SWE-QA questions:** requests 3, flask 3, pytest 2, django 2.

The seed (`20261118`) and the stratified ordering are unchanged, and both conditions (M and B2) use the same ids.

**Consequence for the analysis.** With n=10 per dataset, the McNemar and Wilcoxon tests have very low power: even a 30-point accuracy difference is unlikely to reach p<0.05.
- H1 and H3 are still tested as pre-registered.
- Day-1 results are reported as **exploratory**: effect sizes, Wilson/bootstrap CIs, cost and qualitative trajectory analysis.
- A null result must not be read as evidence of no effect.

## Amendment 2 (2026-11-18, registered before any sweep run; the main run M had started, B2 had not)
The user asked to test the optimal number of agents. This is added as an **exploratory sensitivity analysis**; no confirmatory hypothesis is attached to it.

- **Knob.** `swarm.max_subagents`, the hard cap on spawned subagents. Tasks beyond the cap queue and are handed to freed workers.
  - `swarm.max_teammates` was also considered. It is accepted by the code but is not used in dynamic mode, as verified in `swarm/tools.py` and `swarm/prompts.py`.
- **Arms.**

  | Arm | Agents |
  |---|---|
  | `M_cap2` | cap 2 |
  | `M_cap4` | cap 4 |
  | `M_cap8` | cap 8 |
  | M | default cap 16 |
  | B2 | single agent, one agent and no orchestration |

  All other settings equal M. All arms use the same 20 question ids.
- **Order.** Run after M and B2 (the user's order: main method, then baseline, then further experiments), within the $50/day cap.
- **Reported per arm:**
  - MultiHop-RAG judge accuracy with Wilson CI, and SWE-QA mean score with bootstrap CI
  - $/question and median latency
  - number of agents actually spawned (`swarm_teammates_spawned`)
  - quality vs cap and quality vs cost curves
- **Paired differences** against M are given with bootstrap CIs and **no significance claims**, since n=20 per arm. "Optimal" is read as the cheapest cap whose quality CI overlaps the best arm's. This is descriptive only.
- We also report the relationship between the number of agents the orchestrator spawns naturally under M and correctness. This is correlational only.
