# Summary of all experiments so far

Last updated: 2026-11-18. Every number is filled from `results/day1/metrics.json` by `scripts/build_paper.py`.

## In one paragraph (plain language)
We took ArcticSwarm, a system where several AI agents research a question in parallel and check each other's work. We pointed it at folders of files on this computer instead of the web: news articles, and real Python code repositories. Every agent used the small, cheap Claude Haiku 5.5 model. Agents could search the files, read them, and run any command or Python code in a locked-down Linux sandbox.

On 20 test questions, the multi-agent swarm was **not more accurate** than one agent with the same tools:
- **News questions:** {{summary.M.mhr_judge_acc|pct}} for both.
- **Code questions:** under a strict grading rubric the swarm was **worse** ({{summary.M.swe_mean|f1}} vs {{summary.B2.swe_mean|f1}} out of 100), partly because its answers were about five times longer.
- **Cost:** the swarm cost about {{ratios.cost_M_over_B2|f1}}× more per question.

We also varied how many agents the swarm may use: 2, 4, 8, 16 or 32. No setting beat the single agent. With too few agents (2–4) the swarm mostly ran out of time. With more than about 8 nothing changed, because the orchestrator only uses about 6–7 agents anyway.

With only 10 questions per dataset these results are preliminary.

## Experiments

| Id | What | Agents (max) | Questions | Status | Report |
|---|---|---|---|---|---|
| day1-A | ArcticSwarm swarm (M) vs single agent (B2) | 16 vs 1 | 20 paired | done | [day1-main-vs-single-agent.md](experiments/day1-main-vs-single-agent.md) |
| day1-B | Agent-count sweep: swarm cap 2 / 4 / 8 / 32 (+ M = 16, B2 = 1) | 1–32 | 20 paired | done | [day1-agent-sweep.md](experiments/day1-agent-sweep.md) |
| later | B1 BM25 one-shot RAG, C1 closed-book, C2 random chunks, O oracle, B3 compute-matched voting, A1 no code execution, repeat runs | – | – | postponed (user: one main method + one baseline per day, $50/day) | [preregistration.md](preregistration.md) |

## Systems compared ("networks" table)

| System | Architecture | Model / "training" | Objective | Data | Tools | MHR acc. | SWE-QA /100 | $/question |
|---|---|---|---|---|---|---|---|---|
| **M**: ArcticSwarm gated-BBS swarm | Orchestrator + isolated browsing subagents + reviewers/auditor; gated bulletin board | Claude Haiku 5.5, no training (prompted); effort high/medium | Answer the question with file citations + `FINAL ANSWER:` | Folder of files (609 news `.md` / 4 repos) | BM25 search, file fetch, sandboxed bash + Python | {{summary.M.mhr_judge_acc|pct}} | {{summary.M.swe_mean|f1}} | {{summary.M.cost_usd_per_q|usd}} |
| **B2**: ArcticSwarm single agent | One agent, same harness/skills | same | same | same | same | {{summary.B2.mhr_judge_acc|pct}} | {{summary.B2.swe_mean|f1}} | {{summary.B2.cost_usd_per_q|usd}} |
| **T0**: trivial answers (control, no LLM) | Constant / majority answer | none | Probe the metric | MultiHop-RAG queries | none | official metric {{trivial_baselines.constant_hedge.official_overlap|pct1}}, EM {{trivial_baselines.constant_hedge.exact_match|pct1}} | – | 0 |

No model is trained in this project, so "training", "curricula" and "fill/completion" do not apply. The models are used zero-shot, with tools.

## Key terms
- **RAG (retrieval-augmented generation):** the model answers from retrieved documents rather than from memory alone.
- **Agentic RAG:** the model decides what to search and read in a loop, using tools.
- **ArcticSwarm:** a multi-agent research framework ([arXiv:2609.01870](https://arxiv.org/abs/2609.01870)). An *orchestrator* splits the question into tasks. *Subagents* research them and post findings to a *bulletin board (BBS)*. *Reviewers* challenge or verify the findings before a report is written.
- **Isolation / deferred consensus:** isolated subagents can post to the board but cannot read it, so they don't copy each other's early (possibly wrong) guesses.
- **BM25:** a classic keyword-relevance ranking function. Here it is implemented by the `bm25s` library over ~1,500-character chunks of each file.
- **Sandbox (WSL2):** a separate Linux system on the same PC, where agents can run any command and install software. It cannot see Windows files and holds no API keys.
- **Judge:** an LLM (here Haiku 5.5) that grades answers against reference answers.
  - **MultiHop-RAG:** correct or incorrect.
  - **SWE-QA:** a 0–100 rubric over correctness, completeness, relevance, clarity and reasoning.
- **EM (exact match):** the normalized answer string equals the gold answer.
- **Wilson CI:** a confidence interval for a proportion.
- **Bootstrap CI:** a confidence interval from resampling questions.
- **McNemar / Wilcoxon:** paired significance tests for binary outcomes and for scores, respectively.
- **Holm correction:** adjusts p-values when testing several hypotheses.
- **Preregistration:** hypotheses and analysis written down and committed *before* seeing results.

## Where to look
- **Pre-registered plan and amendments:** [preregistration.md](preregistration.md).
- **Running log of decisions:** [plan.md](plan.md).
- **Literature:** [literature-review.md](literature-review.md), [state-of-the-art-review.md](state-of-the-art-review.md).
- **Paper:** [paper/paper.md](paper/paper.md) (and PDF).
