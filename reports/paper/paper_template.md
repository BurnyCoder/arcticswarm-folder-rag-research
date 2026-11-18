---
title: "Deferred-consensus multi-agent research over local folders: adapting ArcticSwarm to retrieval-augmented generation with Claude Haiku 5.5 and sandboxed code execution"
author: "Libor \"Burny\" Burian"
date: "2026-11-18"
---

# Abstract

ArcticSwarm ([Yoon et al. 2026](https://arxiv.org/abs/2609.01870)) is a multi-agent deep-research framework. It defers early consensus: subagents research in isolation and post to a gated bulletin board, and reviewers must challenge or verify candidates before a report is committed. Its published gains come from live-web and fixed-corpus browsing (BrowseComp, BrowseComp-Plus).

We adapt it to retrieval-augmented generation (RAG) over **a local folder of many files**, with no web access. The adaptation adds:
- a BM25 folder-corpus backend with citable `path#Lstart-end` ids
- file reads by path
- **arbitrary bash/Python execution** in an isolated WSL2 sandbox where agents can install any tool

All roles run on `claude-haiku-5-5`.

On a pre-registered, paired 20-question sample (10 MultiHop-RAG multi-hop news questions over 609 article files; 10 SWE-QA repository questions over requests, flask, pytest and django at pinned commits), the full swarm (M) reached:
- **MultiHop-RAG:** {{summary.M.mhr_judge_acc|pct}} judge accuracy (95% CI {{summary.M.mhr_judge_ci|pctci}}), against {{summary.B2.mhr_judge_acc|pct}} ({{summary.B2.mhr_judge_ci|pctci}}) for the single-agent ArcticSwarm harness (B2) with identical tools.
- **SWE-QA:** a rubric score of {{summary.M.swe_mean|f1}}/100, against {{summary.B2.swe_mean|f1}}/100.
- **Cost:** {{summary.M.cost_usd_per_q|usd}} per question, against {{summary.B2.cost_usd_per_q|usd}}.

The pre-registered paired tests:
- MultiHop-RAG, M − B2 = {{tests.H1.diff|pct}}: Holm-adjusted p = {{tests.H1.p_holm|f3}}
- SWE-QA, M − B2 = {{tests.H3.diff|f1}}: Holm-adjusted p = {{tests.H3.p_holm|f3}}

An exploratory agent-count sweep (`swarm.max_subagents` ∈ {2, 4, 8, 16, 32}) found no swarm size that matched the single agent on SWE-QA. Caps below the orchestrator's natural team size (about {{summary.M.agents_spawned_mean|f1}} agents) caused time-limit failures, and caps above it had no effect. With n=10 per dataset these tests are underpowered, and the day-1 results are exploratory. We release the fork, harness, preregistration and all judged outputs.

# 1. Introduction and motivation

"Chat with your folder" is a common RAG use case: answering questions from a directory of documents or a code repository. Two design families compete:
- **Vector or keyword retrieval:** top-k chunks are stuffed into a prompt.
- **Agentic search:** an LLM iteratively runs search tools, reads files and executes code (see [state-of-the-art-review.md](../state-of-the-art-review.md)).

Multi-agent systems add parallel, diverse search. ArcticSwarm's thesis is that diversity must be protected from *premature consensus* (Yoon et al. 2026). Its evidence comes from web-scale questions with obscure answers and frontier models. We ask whether the same orchestration helps in a different regime:
- small, closed folders
- a small, cheap model (Haiku 5.5)
- agents that can run arbitrary code over the files

**Novelty.** To our knowledge this is the first adaptation of ArcticSwarm's gated-BBS orchestration to local-folder RAG with sandboxed arbitrary code execution, evaluated against its own single-agent harness under a preregistration. Contributions:
1. A folder-corpus backend and a WSL2 sandbox execution backend for ArcticSwarm.
2. A reproducible, pre-registered evaluation harness.
3. A day-1 paired comparison of swarm vs single agent.
4. An agent-count sweep (Amendments 2 and 3).

# 2. Background and related work

The full annotated review, with sources, is in [literature-review.md](../literature-review.md).

- **ArcticSwarm** (Yoon et al. 2026):
  - BBS isolation for exploration tasks, reviewer verdicts (Challenge/Alternative/Verified), and verifier-gated reporting.
  - On BrowseComp-Plus with Qwen 3.5-27B it reports a single agent at 48.4%, direct messaging at 61.9%, a duo at 66.1% and the gated BBS at 82.6%.
- **MultiHop-RAG** ([Tang & Yang 2024](https://arxiv.org/abs/2401.15391)): 609 news articles and 2,556 queries; GPT-4 scores 0.56 with retrieved chunks and 0.89 with gold evidence. We found its official word-overlap metric to be gameable (§4.1).
- **SWE-QA** ([Peng et al. 2026](https://arxiv.org/abs/2509.14635)): repository-level code QA with a 5-dimension LLM-judge rubric.
- **Retrieval:** BM25 via bm25s ([Lù 2024](https://arxiv.org/abs/2407.03618)).
- **Code-acting agents:** CodeAct, SWE-agent and OpenHands motivate giving agents a shell and Python.
- **LLM-as-a-judge bias:** self-preference, [Panickssery et al. 2024](https://arxiv.org/abs/2404.13076).

# 3. Method

![Architecture](../figures/architecture.png)

## 3.1 System

The fork lives in the `ArcticSwarm/` submodule, branch `folder-rag`.

- **Folder corpus (`web.corpus_backend: folder`):**
  - Recursive file walk, skipping `.git`, caches and binary files.
  - Text extraction: UTF-8; PDF via pypdf; DOCX/PPTX/HTML via markitdown.
  - Line-aligned chunks of about 1,500 characters with 2 lines of overlap.
  - Identifier splitting: snake_case, camelCase and paths are split, for documents and queries alike.
  - BM25 via bm25s, with English stopwords and the Snowball stemmer.
- **Search and fetch:**
  - `web_search` returns `path (lines a-b)` and a `corpus://folder/<path>#La-b` id.
  - `web_fetch` reads a file or line span by id, paged at the tool-output cap.
  - The tool names are kept because ArcticSwarm's review gates are keyed on them.
- **Code execution (`tools.exec_backend: wsl`):**
  - `bash` and `python_execute` run as root in a dedicated WSL2 Ubuntu 24.04 distro.
  - Isolation: Windows drive automount and interop are disabled, and no Windows environment (no API keys) is forwarded.
  - Agents may `apt-get` or `pip install` anything; a `packages=` argument covers Python libraries.
  - A soft proxy guard allows only package hosts.
  - Before every run the corpus is copied into the sandbox and SHA-256 verified.
- **Model:** `claude-haiku-5-5` for every role.
  - Adaptive thinking; effort `high` for the orchestrator and `medium` for subagents and the auditor.
  - Context compaction at 90K tokens, to stay on the ≤100K-token price card.
  - The source scorer is disabled.
  - An API probe showed that Haiku 5.5 rejects ArcticSwarm's `budget_tokens` thinking, so the client was patched.
- **Prompts and skills:** folder-specific identity and skills. The web-specific heuristics (region and language pivots, anti-fame bias, "always one answer") were removed, because a folder may not contain the answer.

## 3.2 Conditions
- **M:** the full gated-BBS swarm (`conf/bench/folder_rag.yaml`).
- **B2:** ArcticSwarm single agent (`swarm.enabled=false`) with identical tools, skills, model and effort.
- **Agent-count sweep:** `swarm.max_subagents` ∈ {2, 4, 8, 32}, against the default of 16 in M (Amendments 2 and 3).

## 3.3 Data and sampling
- 10 MultiHop-RAG questions, stratified by question type: inference 3, comparison 4, temporal 2, null 1.
- 10 SWE-QA v2 questions: requests 3, flask 3, pytest 2, django 2.
- Seeded stratified ordering with seed 20261118.
- The MultiHop-RAG articles are written as `<source>/<date>_<title>.md` files with a metadata header. The SWE-QA repositories are cloned at the benchmark's pinned commits.

## 3.4 Metrics and analysis (pre-registered)
- **MultiHop-RAG:** strict binary judgement of the extracted `FINAL ANSWER:` line by a Haiku 5.5 judge with JSON structured output. A missing line counts as incorrect. Secondary metrics: normalized exact match and the official word-overlap metric.
- **SWE-QA:** the paper's 5-dimension rubric, copied verbatim, judged by Haiku 5.5; scored 0–100.
- **Tests:**
  - H1: exact McNemar test.
  - H3: Wilcoxon signed-rank test.
  - Holm correction over {H1, H3}.
  - Wilson and paired-bootstrap 95% CIs (10,000 resamples).
- **Cost:** API list price × token usage, from the full LLM-call logs.

# 4. Results

{{TABLES}}

![Main results](../../results/day1/fig_main.png)

![Per-question outcomes](../../results/day1/fig_per_question.png)

## 4.1 Metric validity (no API calls)
- The official MultiHop-RAG metric counts an answer as correct if any gold word appears in it. Under it, the constant string "yes no insufficient sam google" scores {{trivial_baselines.constant_hedge.official_overlap|pct1}} on all 2,556 queries. Answering each question type's majority answer scores {{trivial_baselines.majority_per_type.official_overlap|pct1}}. Under normalized exact match the same two strategies score {{trivial_baselines.constant_hedge.exact_match|pct1}} and {{trivial_baselines.majority_per_type.exact_match|pct1}}.
- The official metric is therefore unusable as a primary metric.
- On our sample the judge agreed with exact match on {{summary.M.judge_em_agreement|pct}} of M's MultiHop-RAG answers. The disagreements are mostly label-style answers, e.g. "yes" for a gold "Align".

## 4.2 Swarm vs single agent
**MultiHop-RAG.**
- The swarm and the single agent both reached {{summary.M.mhr_judge_acc|pct}}, with *identical* per-question outcomes.
- Gold evidence files appeared in {{summary.M.mhr_evidence_recall|pct}} (M) and {{summary.B2.mhr_evidence_recall|pct}} (B2) of trajectories.
- The three shared errors are therefore verdict errors on retrieved evidence: a yes/no comparison answered "no", another answered "Insufficient information", and a "Yes; No" hedge.
- **H1 is not supported** (McNemar p = {{tests.H1.p|f3}}).

**SWE-QA.**
- The swarm scored {{summary.M.swe_mean|f1}} and the single agent {{summary.B2.swe_mean|f1}}.
- Difference: {{tests.H3.diff|f1}} points, 95% CI {{tests.H3.ci|f1ci}}, Holm-adjusted p = {{tests.H3.p_holm|f3}}.
- This is a significant difference **opposite** to H3, i.e. a negative result.
- **Exploratory, post hoc:**
  - The swarm's reports were much longer (median {{summary.M.resp_chars_median_swe|int}} vs {{summary.B2.resp_chars_median_swe|int}} characters).
  - Length correlated negatively with score (Spearman ρ = {{exploratory_length_vs_score.spearman_rho|f2}}).
  - The swarm's largest per-dimension gaps were on clarity ({{summary.M.swe_dims.clarity|f1}} vs {{summary.B2.swe_dims.clarity|f1}}) and relevance ({{summary.M.swe_dims.relevance|f1}} vs {{summary.B2.swe_dims.relevance|f1}}), not correctness ({{summary.M.swe_dims.correctness|f1}} vs {{summary.B2.swe_dims.correctness|f1}}).
  - So the deficit is at least partly a report-format effect under a strict rubric.
- **No-tool case.** In one swarm case the orchestrator answered from parametric memory without delegating any search, and the verifier gate did not catch it.

**Cost.** The swarm cost {{ratios.cost_M_over_B2|f1}}× as much per question ({{summary.M.cost_usd_per_q|usd}} vs {{summary.B2.cost_usd_per_q|usd}}) and took {{ratios.latency_M_over_B2|f1}}× the median latency.

## 4.3 Agent-count sweep
![Agent-count sweep](../../results/day1/fig_agent_sweep.png)

- **Caps of 8 or more never bind.**
  - The orchestrator chose to spawn {{summary.M_cap8.agents_spawned_mean|f1}} (cap 8), {{summary.M.agents_spawned_mean|f1}} (cap 16) and {{summary.M_cap32.agents_spawned_mean|f1}} (cap 32) agents per question.
  - So arms 8, 16 and 32 are effectively the same system. Their quality differences are within noise: SWE-QA {{summary.M_cap8.swe_mean|f1}} / {{summary.M.swe_mean|f1}} / {{summary.M_cap32.swe_mean|f1}}; cap 32 − M = {{sweep_vs_M.M_cap32.H3.diff|f1}}, CI {{sweep_vs_M.M_cap32.H3.ci|f1ci}}.
  - This confirms the expectation written in Amendment 3 before cap 32 ran.
- **Caps below the natural team size starve the swarm of time.** The orchestrator still plans for about 6–7 workers.
  - With 2 or 4 agents, tasks queue: {{summary.M_cap2.hit_time_limit|int}}/20 (cap 2) and {{summary.M_cap4.hit_time_limit|int}}/20 (cap 4) questions hit the 900 s budget, against {{summary.M.hit_time_limit|int}}/20 at cap 16.
  - At cap 2, {{summary.M_cap2.errors|int}} questions timed out completely, even after the wrap-up phase. They are scored as failures, as pre-registered.
  - Cap 2 is the worst arm: MultiHop-RAG {{summary.M_cap2.mhr_judge_acc|pct}}, SWE-QA {{summary.M_cap2.swe_mean|f1}}.
  - Cap 4 is cheaper ({{summary.M_cap4.cost_usd_per_q|usd}}/q) and on MultiHop-RAG nominally the best arm ({{summary.M_cap4.mhr_judge_acc|pct}}, one more question right), but it ran up against the time budget on most questions.
- **Cost is not monotone in the cap.** Small caps cost less per question but take the longest wall-clock time, because the same work is serialised and then cut off.
- **"Optimal" by the pre-specified rule** (the cheapest arm whose quality CI overlaps the best arm's):
  - **MultiHop-RAG:** all arms overlap, so the cheapest arm, the **single agent (1 agent)**, is optimal.
  - **SWE-QA:** the single agent is best ({{summary.B2.swe_mean|f1}}, CI {{summary.B2.swe_ci|f1ci}}), and no swarm arm's CI overlaps it.
  - So on this setup the optimal number of agents is **one**.
  - If a swarm is used, a cap at or above its natural team size (≥ 8 here) avoids time-limit failures. Raising the cap further changes nothing, because the orchestrator doesn't use the extra agents.
- **Caveats.** n = 10 per dataset per arm and a single run. Caps 2/4/8 ran concurrently, though per-call latency was checked and unchanged. The time budget (900 s + 300 s wrap-up) interacts with the cap, so a longer budget could change the low-cap arms.

# 5. Discussion and limitations
- **Main finding.**
  - On small local folders with Claude Haiku 5.5 and code-capable tools, ArcticSwarm's deferred-consensus orchestration did not improve accuracy over its own single-agent harness.
  - It was worse under the SWE-QA rubric.
  - It cost {{ratios.cost_M_over_B2|f1}}× more and took {{ratios.latency_M_over_B2|f1}}× longer.
- **Why the paper's gains may not transfer here** (a mechanism hypothesis, not tested here):
  - ArcticSwarm targets questions whose answers are obscure and hard to find, where independent search adds recall.
  - In our folders a single agent with `rg`/BM25 already found the gold evidence files ({{summary.B2.mhr_evidence_recall|pct}} recall on MultiHop-RAG), so extra searchers had little to add.
  - The remaining errors were verdict errors, which the reviewers did not fix.
- **Report format matters under rubric judges.** The swarm's long, citation-heavy reports scored lowest on clarity and relevance. This interacts with the judge's strictness, and a length-controlled comparison is needed (to-do).
- **Engineering lessons.** Running ArcticSwarm with a new model and on a new OS surfaced:
  - API-shape incompatibilities (Haiku 5.5 rejects `budget_tokens`)
  - a silent credential-leak path (the Anthropic key sent to OpenAI)
  - a disabled fallback ladder
  - a gameable benchmark metric

  Each was found by probing or by reading code and logs, and is documented in the experiment report.

**Limitations.**
- n = 10 per dataset per arm, from a single run.
- A same-family LLM judge (Haiku 5.5). Self-preference bias affects all arms equally, but limits comparison with published numbers.
- The SWE-QA rubric judge differs from the paper's.
- Contamination: both benchmarks predate the model's training data. The closed-book control is postponed.
- BM25 only.
- A soft network guard.
- Budgets lower than the paper's (900 s per question).
- Several pre-registered baselines and the no-code ablation are postponed to later days, at the user's budget constraint.

# 6. Conclusion
We adapted ArcticSwarm to RAG over local folders, with sandboxed code execution and Claude Haiku 5.5 throughout, and evaluated it under a preregistration.
- **Swarm vs single agent.** In this regime the full swarm matched the single agent on multi-hop news QA, scored lower on repository QA, and cost about {{ratios.cost_M_over_B2|f1}}× more.
- **Agent-count sweep.** No swarm size beat the single agent. Caps below the orchestrator's natural team size of about 6–7 agents caused time-limit failures, and caps above it had no effect.
- **Practical advice for folder RAG with a small model:** start with a single code-capable agent.

The fork, harness, preregistration and all judged outputs are released (privately) for replication and extension.

# Appendix A. Reproducibility
- **Code and settings.**
  - Commands: `folderrag prepare`, `folderrag run M`, `folderrag run B2`, `folderrag run M_cap{2,4,8}`, `folderrag judge`, `folderrag analyze`, then `python scripts/build_paper.py`.
  - Everything is pinned in `uv.lock`, the fork commit in the submodule, and `ArcticSwarm/conf/bench/folder_rag.yaml`.
- **Logs.** Raw runs, trajectories and full LLM-call logs are under `D:\AI\arcticswarm-folder-rag\runs` and `\logs`. Judged outputs are in `results/day1/judged.jsonl`.

# AI statement
Claude Code (Anthropic) wrote this codebase and this paper. Human clean-up and rewriting are in progress. A human, Libor Burian, provided the exact specification that Claude Code executed: the task, the constraints, the budget and the run order.
