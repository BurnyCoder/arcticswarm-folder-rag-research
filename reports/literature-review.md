# Literature review: ArcticSwarm-style multi-agent agentic RAG over local folders

Last updated: 2026-11-18

**Summary.** ArcticSwarm ([Yoon et al., arXiv:2609.01870v2](https://arxiv.org/html/2609.01870v2)) is a multi-agent deep-research framework. During search, subagents post to a shared bulletin board but cannot read it. A three-step integration gate then has to pass before the swarm commits to an answer. It reports 82.6% on BrowseComp-Plus with Qwen 3.5-27B, against 48.4% for its own single agent and 62.5% for compute-matched majority voting. We adapt it to local-folder RAG: BM25 search, file fetch and a bash/python sandbox, run on Claude Haiku 5.5, and evaluated on MultiHop-RAG and SWE-QA. The literature points to four design constraints:
(i) MultiHop-RAG's official QA metric is a whitespace-token-overlap test. By our own computation, trivial answers score 55% under it, and a constant hedge string scores 86%. Answers therefore need strict extraction and exact match.
(ii) The SWE-QA v2 judge is Claude Sonnet 4.5, which is in the same model family as our agent, so self-preference and preference-leakage bias is a live risk.
(iii) Both benchmarks predate Haiku 5.5's June 2026 training cutoff, so closed-book scores mix reasoning with memorization.
(iv) The full ArcticSwarm configuration used about 25M tokens and a median of 104 minutes per question. This forces subsampling and a reduced budget.

**How this review was produced.** Every number below was read from the cited page (arXiv HTML/PDF, GitHub source, HF dataset card, or vendor docs) on 2026-11-18. Numbers marked **"(our computation)"** were derived by us from public data or code on that date, and the method is stated next to each one. Claims we could not verify are marked **[unverified]**.

---

## 1. ArcticSwarm (the framework we adapt)

- **Source.** Yoon, Liu, Wang, Wu, Xu, Kuang, Hwang, He, Yao. *ArcticSwarm: Deferring Early Consensus in Long-Horizon Multi-Agent Research.* [arXiv:2609.01870](https://arxiv.org/abs/2609.01870), cs.MA. v1 is dated 2026-09-01 and v2 is dated 2026-11-11; we read [v2 HTML](https://arxiv.org/html/2609.01870v2). The code is at [Snowflake-AI-Research/ArcticSwarm](https://github.com/Snowflake-AI-Research/ArcticSwarm) under Apache-2.0. The README we read is from commit `5f364e2` (2026-09-03), vendored here as a submodule.
- **Problem framing.** Coding tasks have verifiers. Long-horizon web search does not, so systems fall back on voting. Majority voting cannot surface an answer that no single run reached. Agents that can read each other's findings also adopt an early candidate before alternatives have been tested. The paper calls this **early consensus** ([abstract](https://arxiv.org/abs/2609.01870)).
- **Method** (Sec. 3 of [v2](https://arxiv.org/html/2609.01870v2)):
  - **Bulletin board.** A single bulletin board (BBS) carries all inter-agent communication. Each posted finding includes evidence, a confidence score and sources.
  - **Orchestrator.** The orchestrator decomposes the question into tasks and never searches itself. Each task gets a **profile** (browsing or reasoning) and an **access mode**. A deterministic harness, not the LLM, assigns tasks to subagents and decides whether a run may answer.
  - **Gathering gate (isolation vs collaboration).** *Isolation* tasks can post to the board but cannot read it during the task. *Collaboration* tasks read the board. Isolation only blocks new board reads: 14.8% of isolated tasks still named a board candidate in their task text (Sec. I.5).
  - **Integration gate, three steps.**
    1. *Self-check:* the subagent scores its candidate against each constraint.
    2. *Board check:* builders and at least one *dedicated reviewer*, which takes no build tasks, issue verdicts. **Challenge** means a failed constraint or weak source, **Alternative** means a different candidate, and **Verified** means every constraint is confirmed with specific evidence.
    3. *Answer check:* the report tool stays hidden until there is at least one builder Verified, one dedicated-reviewer Verified and one alternative-candidate task (Eq. 1, n_b ≥ 1 ∧ n_d ≥ 1 ∧ n_alt ≥ 1). These conditions become advisory after a 300 s wait. A failed post-answer check reopens search instead of only rejecting the candidate.
  - **Budgets** (Sec. 4):
    - up to 16 subagents per question;
    - 200 turns per subagent and 1,200 turns for the orchestrator;
    - 16,384 maximum output tokens;
    - 20,000 s per question on BrowseComp-Plus;
    - structured compaction when context grows too long;
    - a document scorer that annotates, but never gates, retrieved documents.
- **BrowseComp-Plus retriever.** Hybrid BM25 + Arctic Embed L v2.0 with an internal reranker. The authors note this is weaker than the Qwen3-Embedding-8B used by typical baselines ([v2](https://arxiv.org/html/2609.01870v2), Sec. 4 and Table 25).
- **Judge.** GPT-4.1 with the official BrowseComp(-Plus) grading prompt (App. G.1.1).
- **Key results.** All values below were verified by parsing [v2](https://arxiv.org/html/2609.01870v2) Tables 1, 2 and 4; full tables are in the [SOTA review](state-of-the-art-review.md).
  - **BrowseComp-Plus (830 questions):**

    | Model | ArcticSwarm | MiroFlow | Published |
    |---|---|---|---|
    | GPT-5 | 88.3% | 66.0% | 72.9% |
    | Sonnet 4.5 | 80.0% | 61.0% | 67.2% |
    | Qwen 3.5-27B | 82.6 ± 0.5% | 70.6 ± 3.7% | n/a |

    The "Published" scores come from the Claude Opus 4.5 System Card, as cited in Table 1.
  - **Communication-mode ablation (Table 2, Qwen 3.5-27B, 830 questions, mean ± SD over 3 runs):**

    | Configuration | Accuracy | Relative tokens |
    |---|---|---|
    | Single agent | 48.4 ± 1.0 | 0.05x |
    | Direct messaging | 61.9 ± 0.7 | 1.14x |
    | Duo (leader + auditor) | 66.1 ± 1.3 | 0.31x |
    | **Gated BBS** | **82.6 ± 0.5** | 1x |
    | Majority@20 single agents (matched budget) | 62.5 | 1x |
    | Without gathering gate | 78.8 ± 1.0 | |
    | Without integration gate (gathering gate on) | 76.6 ± 0.4 | |
    | Without both gates | 74.5 ± 0.8 | |

    The paper reports Holm-adjusted p < 0.05 for the gate ablations.
  - **Live-web BrowseComp (1,266 questions):** 73.6% with GPT-5 and 50.2% with Sonnet 4.5 (Table 4).
  - **Early consensus, measured directly.** When the first board candidate was wrong, runs kept it 22.3% of the time with the gathering gate and 32.2% without it. The paired difference is −9.9 points [−13.8, −6.1] (Sec. 5.3 / I.9).
  - **Reviewer diversity (App. D, GPT-5 runs where the gate was not enforced; correlational only).**
    - On BrowseComp, accuracy was 86.4% when both a builder and a dedicated reviewer posted Verified, and 35.3% when neither did.
    - On BrowseComp-Plus, accuracy was 91.4% when an alternative-candidate task existed and 26.8% when none did.
    - These buckets are self-selected (easy questions attract Verified verdicts), so they are not causal evidence.
- **Cost (Table 21, Qwen 3.5-27B, BrowseComp-Plus, verified by parsing v2):**

  | Configuration | Accuracy | Tokens per question | Median min per question |
  |---|---|---|---|
  | Full swarm | 82.6% | 24.86M | 104.4 |
  | Without the answer check | 80.4% | 18.85M | 26.4 |
  | Without both gates | 74.5% | 5.06M | 16.8 |
  | Duo | 66.1% | 7.69M | 10.0 |
  | Direct messaging | 61.9% | 28.38M | 38.9 |

  Dropping only the answer check costs 2.2 points and cuts wall-clock time by about 4x, which makes it the obvious budget lever. No dollar costs are reported.
- **Statistics protocol, worth copying:** three runs per configuration, 95% question-bootstrap CIs (100,000 resamples), exact sign-flip tests with Holm correction, and development on the first 100 BrowseComp-Plus questions with results also reported on the remaining 730.
- **Failure analysis.** On GPT-5 BrowseComp, 50.4% of failures were confident-wrong, and the reference answer appeared somewhere in the trajectory in 58% of failures (App. K.4). The authors call these *verification* failures rather than *retrieval* failures. Twenty independent single-agent runs share retrieved documents with a mean pairwise Jaccard of 0.178. After adjusting for that overlap, they amount to only about 4.6 independent runs, and majority voting saturates near 62–63% (App. H.1).
- **Discrepancy noted.** The README (Sep 2026) gives MiroFlow's single-agent harness as 57.4%, but v2 Table 2 gives 54.1 ± 0.9. We treat v2 as authoritative.
- **Relevance to us.**
  - The single-agent, gated-BBS and ablation conditions map directly onto ArcticSwarm's Table 2. Its single-agent vs swarm gap (+34.2 points) is the effect size we test for transfer to local-folder RAG.
  - The repo already ships a pluggable `local` corpus backend for BrowseComp-Plus ([README §5](https://github.com/Snowflake-AI-Research/ArcticSwarm)), which can serve as the template for our BM25 tool.
  - The token and latency budget makes full-benchmark runs on 2,556 + 720 questions expensive. The repo's "efficient" preset (fewer subagents, scorer off) and the Duo baseline (0.31x tokens) are cheaper reference points.
  - Rough scale (our computation): 24.86M tokens at Haiku 5.5's listed base input price of "from $0.10/MTok" ([Anthropic models overview](https://platform.claude.com/docs/en/about-claude/models/overview)) is about $2.5 per question. This ignores caching discounts and output pricing, so it is an order-of-magnitude figure only.

## 2. BrowseComp and BrowseComp-Plus

### 2.1 BrowseComp (live web)
- **What.** OpenAI's browsing benchmark of 1,266 questions with short, verifiable answers that require persistent, creative search. Wei et al., 2025, [arXiv:2504.12516](https://arxiv.org/abs/2504.12516).
- **Key numbers** ([HTML](https://arxiv.org/html/2504.12516), Table 3):

  | System | Accuracy |
  |---|---|
  | GPT-4o | 0.6% |
  | GPT-4o with browsing | 1.9% |
  | GPT-4.5 | 0.9% |
  | o1 | 9.9% |
  | Deep Research | 51.5% |

  Deep Research was trained on data targeting BrowseComp-like tasks. Aggregating 64 Deep Research samples by majority voting, weighted voting or best-of-N improves accuracy by "15% to 25%", and best-of-N is best. Exact per-method values appear only in Fig. 4.
- **Grading.** An LLM judge uses the Humanity's Last Exam grading prompt. The judge model is not named in the text.
- **Relevance.** This is the origin of the "voting helps but saturates" argument that ArcticSwarm builds on.

### 2.2 BrowseComp-Plus (fixed corpus)
- **What.** BrowseComp-Plus fixes BrowseComp's live-web retrieval to a corpus, which makes runs reproducible and separates retriever effects from agent effects. Chen, Ma, Zhuang, et al., [arXiv:2508.06600](https://arxiv.org/abs/2508.06600) (v1, 2025-08-08). It was published at [ACL 2026 (long), pp. 22349–22370](https://aclanthology.org/2026.acl-long.1023/) under a revised title ("A Fair and Disentangled Evaluation Benchmark for Deep Search Agents"). The corpus is [Tevatron/browsecomp-plus-corpus](https://huggingface.co/datasets/Tevatron/browsecomp-plus-corpus) (MIT license).
- **Construction** ([HTML v1](https://arxiv.org/html/2508.06600v1)):
  - 830 queries (1,005 reached human verification and 830 passed).
  - 100,195 documents, averaging 5,179.2 words each.
  - Per query, on average: 6.1 evidence documents, 2.9 gold documents and 76.28 hard negatives.
  - Evidence was collected with o3 plus web search and verified by 14 annotators over more than 400 hours.
  - Hard negatives come from GPT-4o sub-query decomposition and SerpAPI.
  - The judge is GPT-4.1.
- **BM25 vs dense retrieval, the central finding** (end-to-end accuracy, same agent):

  | Agent | BM25 | Qwen3-Embedding-8B |
  |---|---|---|
  | GPT-5 | 55.90% | 70.12% |
  | o3 | 49.28% | 63.49% |
  | Sonnet 4 | 14.34% | 36.75% |
  | Opus 4 | 15.54% | 36.14% |
  | Search-R1-32B | 3.86% | 10.36% |

  On retriever-only evaluation with the full question as the query, BM25 reaches evidence nDCG@10 of 1.6, against 20.3 for Qwen3-Embed-8B.
- **Leaderboard.** The [live leaderboard](https://tevatron-browsecomp-plus.hf.space) re-judges entries with Qwen3-32B instead of GPT-4.1 and states that the two judges differ by less than 1% ([metrics.md](https://huggingface.co/spaces/Tevatron/BrowseComp-Plus/blob/main/public/blobs/metrics.md)). Top entries as of 2026-11-18 are listed in the [SOTA review](state-of-the-art-review.md).
- **Relevance.**
  - BrowseComp-Plus is the direct precedent for "deep research over a fixed local corpus".
  - It shows that **retriever quality dominates when the agent's only tool is BM25 top-k**.
  - Later leaderboard entries recover much of the gap with richer tools (`get_document`, REPL code execution) and query expansion. Section 4 lists examples. This motivates our `fetch`, `bash` and `python` tools and the no-code-execution ablation.

## 3. RAG and lexical-retrieval foundations

- **RAG (Lewis et al., NeurIPS 2020).** [arXiv:2005.11401](https://arxiv.org/abs/2005.11401). A seq2seq generator is combined with a dense-vector index of Wikipedia accessed by a pre-trained neural retriever. One variant conditions on the same passages for the whole output and the other on different passages per token. The abstract reports state-of-the-art results on three open-domain QA tasks. Our "BM25 one-shot RAG" condition is the retrieve-then-read baseline in this lineage.
- **BM25 (Robertson & Zaragoza, 2009).** *The Probabilistic Relevance Framework: BM25 and Beyond*, Foundations and Trends in IR 3(4):333–389, [doi:10.1561/1500000019](https://doi.org/10.1561/1500000019); we read the [author PDF](https://staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf).
  - Eq. 3.15 gives the classic weight: tf / (k1·((1−b) + b·dl/avdl) + tf) × w_RSJ.
  - Sec. 3.5 says that "in general values such as 0.5 < b < 0.8 and 1.2 < k1 < 2 are reasonably good in many circumstances", while noting that optimal values depend on the documents and queries.
  - This is our default parameter range.
- **BM25S (Lù, 2024).** [arXiv:2407.03618](https://arxiv.org/abs/2407.03618), [code](https://github.com/xhluca/bm25s) (MIT license).
  - BM25S scores eagerly at index time into sparse matrices, so it needs only NumPy and SciPy.
  - It reports up to 500x the throughput of Rank-BM25 and more than 100x on 10 of 14 BEIR datasets.
  - It reaches an average BEIR nDCG@10 of 39.7 (Lucene variant, k1 = 1.5, b = 0.75), in the same range as other implementations (Elastic 42.0) ([HTML](https://arxiv.org/html/2407.03618), Tables 1 and 3).
  - It implements Lucene (the default), Robertson, ATIRE, BM25L and BM25+, and supports memory-mapped indexes ([README](https://github.com/xhluca/bm25s)).
  - **Relevance:** this is our BM25 implementation choice.

## 4. Agentic and iterative RAG

| Work | Method | Key reported result | Relevance |
|---|---|---|---|
| ReAct, Yao et al., ICLR 2023, [arXiv:2210.03629](https://arxiv.org/abs/2210.03629) | Interleaves reasoning traces with tool actions (a Wikipedia API on HotpotQA and FEVER) | +34 and +10 absolute points over imitation and RL methods on ALFWorld and WebShop. The abstract gives no HotpotQA number. | Our single-agent loop is a ReAct-style tool loop. |
| IRCoT, Trivedi et al., ACL 2023, [arXiv:2212.10509](https://arxiv.org/abs/2212.10509) | Retrieves again after each chain-of-thought step | Up to +21 points on retrieval and +15 on QA with GPT-3 (HotpotQA, 2WikiMultihopQA, MuSiQue, IIRC) | Multi-hop questions benefit from iterative retrieval. This is directly relevant to MultiHop-RAG. |
| FLARE, Jiang et al., EMNLP 2023, [arXiv:2305.06983](https://arxiv.org/abs/2305.06983) | Predicts the next sentence and retrieves again when it contains low-confidence tokens | Superior or competitive results on 4 long-form tasks; the abstract gives no numbers | Retrieval triggered by uncertainty |
| Self-RAG, Asai et al., [arXiv:2310.11511](https://arxiv.org/abs/2310.11511) | Trained LM with reflection tokens that decide when to retrieve and critique evidence | 7B and 13B models beat ChatGPT and RAG-Llama2 on open-domain QA, reasoning and fact verification (abstract) | Self-critique of evidence, comparable to ArcticSwarm's self-check step. Venue not verified on the pages we read. |
| Search-o1, Li et al., [arXiv:2501.05366](https://arxiv.org/abs/2501.05366) | Agentic search inside a large reasoning model, with a "Reason-in-Documents" filter | Strong results on science, math and code plus 6 open-domain QA sets; the abstract gives no numbers | Noise filtering of retrieved documents |
| Search-R1, Jin et al., [arXiv:2503.09516](https://arxiv.org/abs/2503.09516) (v5, Aug 2025) | RL-trained search-query generation with retrieved-token masking | +41% (Qwen2.5-7B) and +20% (3B) relative to RAG baselines on 7 QA sets. Only 3.86% on BrowseComp-Plus with BM25 ([BC-Plus](https://arxiv.org/abs/2508.06600)). | Shows that agentic RAG trained on short QA does not transfer to hard deep research. |
| Recursive Language Models, Zhang, Kraska, Khattab, [arXiv:2512.24601](https://arxiv.org/abs/2512.24601) (v3, May 2026) | The prompt or corpus lives as a variable in a Python REPL that the model inspects programmatically, with recursive sub-calls | For GPT-5, median gains of +26% over compaction, +130% over CodeAct with sub-calls and +13% over Claude Code on 4 long-context tasks. RLM scaffolds also appear on the BrowseComp-Plus leaderboard ([SOTA review](state-of-the-art-review.md)). | Closest precedent for our "python over the folder" tool. |

## 5. Self-consistency, multi-agent debate, and premature consensus

- **Self-consistency (Wang et al., ICLR 2023).** [arXiv:2203.11171](https://arxiv.org/abs/2203.11171). Samples several chain-of-thought paths and takes the majority answer. Gains over greedy CoT: +17.9 (GSM8K), +11.0 (SVAMP), +12.2 (AQuA), +6.4 (StrategyQA) and +3.9 (ARC-c). This is the voting baseline ArcticSwarm argues against for long-horizon search; it works when correctness correlates with agreement.
- **Multiagent debate (Du et al., ICML 2024).** [arXiv:2305.14325](https://arxiv.org/abs/2305.14325); venue and setup from the [project page](https://composable-models.github.io/llm_debate/). Model instances debate until they converge on one answer, using three agents and two rounds in the main experiments. The abstract reports improved math and strategic reasoning and factuality.
- **Evidence that debate and voting are weaker than they look, or converge prematurely:**
  - Smit et al., [arXiv:2311.17371](https://arxiv.org/abs/2311.17371): multi-agent debate does not reliably beat self-consistency or ensembling. It is more hyperparameter-sensitive, and tuning the agents' agreement level helps.
  - Choi, Zhu, Li, NeurIPS 2025 Spotlight, [arXiv:2508.17536](https://arxiv.org/abs/2508.17536): across 7 benchmarks, "Majority Voting alone accounts for most of the performance gains" attributed to debate. Debate induces a martingale over beliefs, so on its own it does not raise expected correctness.
  - Wynn, Satija, Hadfield, ICML MAS Workshop 2025, [arXiv:2509.05396](https://arxiv.org/abs/2509.05396): debate can lower accuracy over rounds. Models switch from correct to incorrect answers after seeing peer reasoning, which the authors link to sycophancy and conformity.
  - Weng, Chen, Wang, ICLR 2025 Oral, [arXiv:2501.13381](https://arxiv.org/abs/2501.13381) (BenchForm): LLM agents show conformity in multi-agent protocols. Enhanced personas and reflection reduce it; the abstract gives no numbers.
  - ArcticSwarm's own measurement (Section 1): reading the board raises the rate of keeping a wrong first candidate from 22.3% to 32.2%.
- **MiroFlow (Su et al., 2026).** [arXiv:2602.22808](https://arxiv.org/abs/2602.22808), [code](https://github.com/MiroMindAI/miroflow).
  - An open-source hierarchical deep-research framework with an agent graph, an optional "heavy-reasoning" mode (ensemble with majority or weighted voting plus a verification loop) and avg@3 reporting ([HTML](https://arxiv.org/html/2602.22808), Secs. 3.4 and 4.1).
  - ArcticSwarm uses it as the strongest open-swarm baseline and cites MiroFlow's GPT-5 BrowseComp result as 63.4% ([ArcticSwarm v2](https://arxiv.org/html/2609.01870v2), Table 4).
  - We could not unambiguously assign 63.4 to a column in MiroFlow's own Table 1 from the HTML extraction **[column assignment unverified]**.
- **Relevance.** Our design should include a compute-matched voting baseline (ArcticSwarm's Majority@k). Otherwise any swarm gain could just be an ensembling gain, as Choi et al. show for debate.

## 6. Code-execution agents and repository-level code QA

- **CodeAct (Wang et al., ICML 2024).** [arXiv:2402.01030](https://arxiv.org/abs/2402.01030). Executable Python is used as the action space. Across 17 LLMs, it reaches up to 20% higher success than JSON or text actions (API-Bank and M3ToolEval). This is the justification for giving agents a python sandbox rather than only fixed tools.
- **SWE-agent (Yang et al., NeurIPS 2024).** [arXiv:2405.15793](https://arxiv.org/abs/2405.15793), [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/5a7c947568c1b1328ccc5230172e1e7c-Abstract-Conference.html). A custom agent-computer interface for navigating, editing and running code. It reported 12.5% pass@1 on SWE-bench and 87.7% on HumanEvalFix at the time. SWE-QA uses a Docker-free adaptation as a baseline.
- **OpenHands (Wang et al., ICLR 2025).** [arXiv:2407.16741](https://arxiv.org/abs/2407.16741). An open platform (MIT license) for agents that write code, use a shell and browse, with sandboxed execution, evaluated on 15 tasks including SWE-bench and WebArena. It is the best open framework on SWE-QA v2 (Section 7.2).
- **Agentless (Xia et al., 2024).** [arXiv:2407.01489](https://arxiv.org/abs/2407.01489). A fixed three-phase pipeline (localization, repair, validation) with no agent loop, reaching 32.00% on SWE-bench Lite at $0.70 per issue. It is a reminder that simple fixed pipelines can rival agents. Our BM25 one-shot RAG is the QA analogue.
- **RepoQA (Liu et al., 2024).** [arXiv:2406.06025](https://arxiv.org/abs/2406.06025). "Searching Needle Function": 500 tasks from 50 repositories in 5 languages, testing 26 LLMs on finding a function from its description. It is a long-context code-search probe rather than open-ended QA.
- **CodeQueries (Sahu et al.).** [arXiv:2209.08372](https://arxiv.org/abs/2209.08372). Extractive span QA over Python files, derived from CodeQL queries, with single-hop and multi-hop questions. Baselines (GPT-3.5, CuBERT) had "limited success". Its scope is file-level, not repository-level.
- **SWE-QA-Pro (Cai et al., 2026).** [arXiv:2603.16124](https://arxiv.org/abs/2603.16124). A newer repository-QA benchmark built from long-tail repositories, which removes questions that direct-answer baselines can solve. It argues popular-repository benchmarks let LLMs rely on memorized knowledge. It reports that agentic workflows beat direct answering by about 13 points for Claude Sonnet 4.5. This is relevant to SWE-QA contamination (Section 9).

## 7. The two benchmarks we use

### 7.1 MultiHop-RAG (Tang & Yang, COLM 2024)
- **Sources.** [arXiv:2401.15391](https://arxiv.org/abs/2401.15391) (v1, 2024-01-27; COLM 2024 acceptance per the [GitHub README](https://github.com/yixuantt/MultiHop-RAG)). Dataset: [HF yixuantt/MultiHopRAG](https://huggingface.co/datasets/yixuantt/MultiHopRAG), ODC-BY license.
- **Data** ([HTML](https://arxiv.org/html/2401.15391v1), Tables 2–4):
  - 609 news articles, each at least 1,024 tokens (mean 2,046.5 tokens), published between 2023-09-26 and 2023-12-26.
  - 2,556 queries: inference 816, comparison 856, temporal 583, null 301.
  - Evidence pieces per non-null query: 2 for 1,078 queries, 3 for 779 and 4 for 398.
  - The HF copy gives 1,079 / 778 / 398 (our computation from the [HF parquet](https://huggingface.co/datasets/yixuantt/MultiHopRAG)), a one-item difference.
  - Each query includes an evidence list (fact, title, source, author, category, published_at, URL), which gives us gold evidence for the oracle condition.
- **Protocol and results.**
  - Retrieval: 256-token chunks via LlamaIndex. The best retrieval setting is voyage-02 + bge-reranker-large, with MRR@10 0.586 and Hits@10 0.7467 (Table 5, null queries excluded).
  - Generation (Table 6): top-6 chunks capped at 2,048 tokens.

    | Model | Retrieved chunks | Ground-truth evidence |
    |---|---|---|
    | GPT-4 | 0.56 | 0.89 |
    | Google-PaLM | 0.47 | 0.74 |
    | ChatGPT | 0.44 | 0.57 |
    | Claude-2.1 | 0.52 | 0.56 |
    | Mixtral-8x7B | 0.32 | 0.36 |
    | Llama-2-70B | 0.28 | 0.32 |

  - The paper does not state the exact matching rule used for Table 6.
- **Official QA metric** ([`qa_evaluate.py`](https://github.com/yixuantt/MultiHop-RAG/blob/main/qa_evaluate.py); the same logic appears in the first committed version, 2024-08-02):
  - A prediction counts as correct if its lowercased **whitespace token set shares any token** with the gold answer.
  - There is no punctuation stripping, and the "answer" is the full output unless it matches the pattern `The answer to the question is "..."`.
- **Answer-format statistics (our computation from the HF parquet, all 2,556 queries):**
  - 1,343 of 2,556 gold answers (52.5%) are "yes" or "no". Comparison queries are 95.9% yes/no (512 yes, 309 no) and temporal queries 89.5% (270 yes, 252 no).
  - Inference answers are concentrated: "Sam Bankman-Fried" is the answer to 275 of 816 (33.7%) and "Google" to 212 (26.0%).
  - Every null query's answer is "Insufficient information."
- **Trivial baselines under the official metric (our computation, same data; script logic copied from `qa_evaluate.py`):**
  - Always answering "Yes": 30.6%.
  - The most common answer for each query type (types are easy to infer from the wording): **55.4%** under token overlap and 53.1% under normalized exact match. This is roughly equal to GPT-4 with retrieved chunks (0.56) in the original paper.
  - The constant string `"yes no insufficient sam google"`: **85.6% under token overlap** (0% exact match).
  - **Implication:** token-overlap scores are gameable by hedged or verbose answers. We must
    1. force a short final-answer field,
    2. score with normalized exact match, with an LLM-judge equivalence check as a secondary metric, and
    3. report per-type majority-class baselines.
- **Relevance.** This is our first benchmark. Its gold evidence enables the oracle condition and its four query types enable per-type analysis. The original paper's 0.56 to 0.89 gap from retrieved to gold evidence shows that retrieval is the bottleneck, which is what agentic search targets.

### 7.2 SWE-QA (Peng et al., ACL 2026 Findings)
- **Sources.** [arXiv:2509.14635](https://arxiv.org/abs/2509.14635); v1 is dated 2025-09-18 and v2 2026-04-26, and we read [v2 HTML](https://arxiv.org/html/2509.14635v2). The ACL 2026 Findings acceptance and pp. 8230–8245 come from the [GitHub README BibTeX](https://github.com/peng-weihan/SWE-QA-Bench). Data: [HF swe-qa/SWE-QA-Benchmark](https://huggingface.co/datasets/swe-qa/SWE-QA-Benchmark), Apache-2.0, updated 2026-08-10. Repository commits are pinned in [`repo_commit.txt`](https://github.com/peng-weihan/SWE-QA-Bench/blob/master/repo_commit.txt).
- **Version caveat.** The arXiv *abstract metadata* still describes v1: 576 QA pairs from 11 repositories, a GPT-5-style judge and scores out of 50 with 1–10 per dimension ([abs page](https://arxiv.org/abs/2509.14635); [v1 HTML](https://arxiv.org/html/2509.14635v1)). The v2 body, HF card and GitHub data describe **720 QA pairs over 15 Python repositories**. Twelve come from SWE-bench (astropy, django, flask, matplotlib, pylint, pytest, requests, scikit-learn, sphinx, sqlfluff, sympy, xarray) and three from SWE-bench-Live (conan, reflex, streamlink). We verified 48 questions per repository in the GitHub JSONL. The v2 statistics table lists flask as 47, a minor inconsistency. **Scores from v1 and v2 are not comparable.**
- **Construction** ([v2](https://arxiv.org/html/2509.14635v2), Sec. 2 and App. A):
  - 77,100 issues were crawled from the 12 SWE-bench repositories and filtered to 41,955, yielding 127,415 extracted questions. These fed a two-level taxonomy: What, Why, Where and How, crossed with 12 intentions. The benchmark samples the four types equally.
  - Questions were instantiated from templates over tree-sitter repository graphs.
  - Initial answers came from a RAG pipeline with a strong LLM. Two experts revised each answer "with the assistance of LLM-powered tools like Cursor", and a third resolved disagreements.
  - Mean answer length is 266.64 words.
  - **The data has only `question` and `answer` fields, with no gold evidence file list** ([HF card](https://huggingface.co/datasets/swe-qa/SWE-QA-Benchmark)). However, 603 of 720 reference answers name at least one `.py` path (our computation, regex `[\w/.-]+\.py\b` over the GitHub JSONL). These counts vary by repository: streamlink 2/48, reflex 12/48, and 45–48 for most others.
- **Evaluation** (v2 Sec. 3 and App. B.2):
  - The judge is **Claude Sonnet 4.5**. It scores 5 dimensions (correctness, completeness, relevance, clarity, and "reasoning", called "coherence" in the text) from 1 to 20 each, for a total out of 100.
  - Each dimension is judged 5 times with majority voting, with anonymized and shuffled candidates.
  - The rubric penalizes content not in the reference (relevance) and answers shorter than the reference.
  - The **released judge script** ([`llm-as-a-judge.py`](https://github.com/peng-weihan/SWE-QA-Bench/blob/master/Benchmark%20construction/score/llm-as-a-judge.py)) uses an env-configured model (its docstring says GPT-5) and makes **a single call per answer**. We found no 5-vote loop. The paper's protocol and the released code may therefore differ.
- **Baselines.** All runs use temperature 0, and OpenHands and SWE-agent are capped at **10 reasoning-action iterations** per question.
  - Direct prompting.
  - Function-chunk RAG and sliding-window RAG: voyage-code-3 embeddings with FAISS, retrieving the top 5; the sliding window is 100 lines ([scripts](https://github.com/peng-weihan/SWE-QA-Bench)).
  - SWE-agent and OpenHands.
  - Commercial tools: Cursor and Tongyi Lingma.
- **Key results (v2 Table 3, total out of 100).**
  - Best per method: Direct 61.41 (GPT-5.1), sliding-window RAG 66.79 (GPT-5.1), SWE-agent 69.85 (GLM-4.6), OpenHands **70.79** (GPT-5.1), Cursor 70.66.
  - Agents gain mostly on correctness and completeness and *lose* on clarity.
  - SWE-bench-Live repositories average 64.98, against 68.59 for SWE-bench repositories. The authors attribute this possibly to reduced leakage (Table 5).
  - The human evaluation (3 engineers, GPT-5.1 answers, 20-point scale) preserves the method ordering but gives higher absolute scores (OpenHands 82.33). **No agreement statistic is reported.**
  - Token use per question: Direct 94 input / 63 output; OpenHands averages 87,045 input / 1,930 output (Table 8).
- **Relevance.**
  - This is our second benchmark. The released baselines are reusable as reference points.
  - Comparing our scores with published ones requires the same judge and protocol; otherwise only within-study comparisons are valid.
  - The missing gold evidence means a SWE-QA "gold-evidence oracle" must be constructed, for example from file paths mentioned in the reference answer. That construction leaks answer content and must be labelled an upper-bound diagnostic, not a fair condition.
  - The 10-iteration cap on the published agents makes them weak baselines relative to an uncapped swarm. Budget-matched comparisons are needed.

## 8. LLM-as-a-judge reliability and bias

- **Zheng et al., NeurIPS 2023 Datasets and Benchmarks.** [arXiv:2306.05685](https://arxiv.org/abs/2306.05685).
  - GPT-4 agrees with human experts 85% of the time on MT-Bench pairwise votes (non-tie setting), against 81% human-human agreement ([HTML v4](https://arxiv.org/html/2306.05685v4), Table 5).
  - Position consistency when answers are swapped: GPT-4 65.0%, GPT-3.5 46.2%, Claude-v1 23.8% (Table 2).
  - Failure rate under a verbosity attack: GPT-4 8.7%, against 91.3% for Claude-v1 and GPT-3.5 (Table 3).
  - Self-enhancement: GPT-4 favoured itself by about 10% and Claude-v1 by about 25%, but the authors could not establish the bias given the limited data.
- **Self-preference bias.**
  - Panickssery, Bowman, Feng, [arXiv:2404.13076](https://arxiv.org/abs/2404.13076): LLMs recognize their own generations, and self-recognition correlates linearly with self-preference after fine-tuning.
  - Wataoka, Takahashi, Ri, NeurIPS 2024 SafeGenAI Workshop, [arXiv:2410.21819](https://arxiv.org/abs/2410.21819): GPT-4 shows significant self-preference, which the authors explain by judges favouring lower-perplexity (more familiar) text.
- **Preference leakage (Li et al., ICLR 2026).** [arXiv:2502.01534](https://arxiv.org/abs/2502.01534). Judges are biased toward models related to them: the same model, an inheritance relationship, or the **same family**. The bias is pervasive and harder to detect than other judge biases.
- **Thakur et al., GEM2 2025.** [arXiv:2406.12624](https://arxiv.org/abs/2406.12624). Only the largest judges approach human alignment, and even they can be up to 5 points off. Percent agreement alone hides large score differences, and judges tend toward leniency.
- **Relevance.**
  - SWE-QA v2's judge (Sonnet 4.5) and our agent (Haiku 5.5) are both Claude models, so the paper-faithful judge is exposed to the same-family preference-leakage effect.
  - Mitigations:
    1. use a non-Anthropic judge as the primary, or at least as a second judge, and report agreement between judges;
    2. calibrate the judge against a small human-labelled subset with a chance-corrected agreement statistic;
    3. check sensitivity to answer length, since the SWE-QA rubric penalizes deviation from the reference length;
    4. keep the judge blind to the condition.
  - For MultiHop-RAG, prefer exact match and use the LLM judge only to adjudicate formatting mismatches.

## 9. Contamination and the closed-book control

- **General.** Sainz et al., EMNLP 2024 Findings, [arXiv:2310.18018](https://arxiv.org/abs/2310.18018), argue that contamination inflates benchmark scores and can invalidate conclusions, and call for per-benchmark measurement. Golchin & Surdeanu, ICLR 2024, [arXiv:2308.08493](https://arxiv.org/abs/2308.08493), detect it with "guided instruction": the prompt names the dataset and partition and gives an initial segment, and the completion is checked against the reference. Their best method reaches 92–100% accuracy against human experts.
- **SWE-bench-specific evidence.**
  - Liang, Garg, Zilouchian Moghaddam, [arXiv:2506.12286](https://arxiv.org/abs/2506.12286): models identify buggy file paths from issue text alone with up to 76% accuracy on SWE-bench, against up to 53% on other repositories. 5-gram reproduction reaches up to 35%, against 18%. This is evidence of memorization of the very repositories SWE-QA uses.
  - SWE-bench-Live (Zhang et al., [arXiv:2505.23419](https://arxiv.org/abs/2505.23419)): 1,319 post-2024 tasks from 93 repositories show a substantial gap relative to static SWE-bench.
- **Timeline.**
  - Claude Haiku 5.5 has a training-data cutoff of June 2026 ([Anthropic models overview](https://platform.claude.com/docs/en/about-claude/models/overview)).
  - The MultiHop-RAG articles (Sep–Dec 2023) and the dataset release (Jan 2024) predate that cutoff.
  - So do SWE-QA v1 (576 items, Sep 2025) and the pinned repository commits, which are public open-source code.
  - The 720-item v2 set is described in arXiv v2 (2026-04-26), but the HF card was last updated on 2026-08-10, after the cutoff. Whether the v2 additions were exposed to Haiku 5.5 is therefore uncertain **[unverified]**.
- **Relevance.**
  - The closed-book condition measures parametric knowledge, including any memorized articles, Q/A pairs or code, not "no retrieval ability".
  - Recommended controls:
    1. a guided-completion probe on a sample of MultiHop-RAG articles and SWE-QA answers;
    2. reporting closed-book accuracy per query type next to the trivial baselines in Section 7.1;
    3. treating the SWE-bench-Live subset (conan, reflex, streamlink) as a lower-contamination slice;
    4. reporting gains over closed-book, not only absolute scores.

## 10. Implications for our experimental design (synthesis)

1. **MultiHop-RAG scoring.** Require a short final-answer field. Use normalized exact match as the primary metric, with token overlap reported only for comparability with the official script. Report the per-type majority-class baseline (53.1% exact match overall, our computation) and an always-abstain baseline for null queries (Section 7.1).
2. **Compute-matched voting baseline.** Add Majority@k of single agents at matched tokens, and report tokens and wall-clock time per condition. Without this, a swarm gain cannot be separated from ensembling (Choi et al.; ArcticSwarm Table 2).
3. **Judge.** On SWE-QA, use a non-Claude primary judge or two judges from different families, report inter-judge and human-judge agreement, and keep the paper's rubric for comparability (Sections 7.2 and 8).
4. **Oracle on SWE-QA.** The benchmark has no gold evidence. Any oracle built from paths in the reference answer is an answer-leaking upper bound, and 117 of 720 items have no `.py` path (our computation).
5. **Contamination.** Interpret closed-book scores as a parametric-knowledge control. Run a memorization probe and report the SWE-bench-Live slice separately (Section 9).
6. **Budget.** Full ArcticSwarm used about 25M tokens and a median of 104 minutes per question on BrowseComp-Plus. Plan a stratified subsample (by query type or repository), fix a per-question token and time cap shared by all agentic conditions, and use paired tests with bootstrap CIs and Holm correction as ArcticSwarm does (Section 1).
7. **Retriever caveat.** BM25 is far weaker than dense retrieval on BrowseComp-Plus (Section 2.2). Our BM25-only tool is a deliberate, simple choice, and the code-execution tools (grep or rg over raw files) are the compensating channel. This makes the no-code-execution ablation essential.

---

## References (all accessed 2026-11-18)

- Yoon et al. 2026, ArcticSwarm, [arXiv:2609.01870](https://arxiv.org/abs/2609.01870); [code](https://github.com/Snowflake-AI-Research/ArcticSwarm)
- Wei et al. 2025, BrowseComp, [arXiv:2504.12516](https://arxiv.org/abs/2504.12516)
- Chen et al. 2025/2026, BrowseComp-Plus, [arXiv:2508.06600](https://arxiv.org/abs/2508.06600); [ACL 2026](https://aclanthology.org/2026.acl-long.1023/); [corpus](https://huggingface.co/datasets/Tevatron/browsecomp-plus-corpus); [leaderboard](https://tevatron-browsecomp-plus.hf.space)
- Lewis et al. 2020, RAG, [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
- Robertson & Zaragoza 2009, BM25, [doi:10.1561/1500000019](https://doi.org/10.1561/1500000019)
- Lù 2024, BM25S, [arXiv:2407.03618](https://arxiv.org/abs/2407.03618)
- Yao et al. 2023, ReAct, [arXiv:2210.03629](https://arxiv.org/abs/2210.03629); Trivedi et al. 2023, IRCoT, [arXiv:2212.10509](https://arxiv.org/abs/2212.10509); Jiang et al. 2023, FLARE, [arXiv:2305.06983](https://arxiv.org/abs/2305.06983); Asai et al. 2023, Self-RAG, [arXiv:2310.11511](https://arxiv.org/abs/2310.11511); Li et al. 2025, Search-o1, [arXiv:2501.05366](https://arxiv.org/abs/2501.05366); Jin et al. 2025, Search-R1, [arXiv:2503.09516](https://arxiv.org/abs/2503.09516); Zhang et al. 2025/2026, RLM, [arXiv:2512.24601](https://arxiv.org/abs/2512.24601)
- Wang et al. 2023, Self-consistency, [arXiv:2203.11171](https://arxiv.org/abs/2203.11171); Du et al. 2024, Multiagent debate, [arXiv:2305.14325](https://arxiv.org/abs/2305.14325); Smit et al., [arXiv:2311.17371](https://arxiv.org/abs/2311.17371); Choi et al. 2025, [arXiv:2508.17536](https://arxiv.org/abs/2508.17536); Wynn et al. 2025, [arXiv:2509.05396](https://arxiv.org/abs/2509.05396); Weng et al. 2025, [arXiv:2501.13381](https://arxiv.org/abs/2501.13381); Su et al. 2026, MiroFlow, [arXiv:2602.22808](https://arxiv.org/abs/2602.22808)
- Wang et al. 2024, CodeAct, [arXiv:2402.01030](https://arxiv.org/abs/2402.01030); Yang et al. 2024, SWE-agent, [arXiv:2405.15793](https://arxiv.org/abs/2405.15793); Wang et al. 2025, OpenHands, [arXiv:2407.16741](https://arxiv.org/abs/2407.16741); Xia et al. 2024, Agentless, [arXiv:2407.01489](https://arxiv.org/abs/2407.01489); Liu et al. 2024, RepoQA, [arXiv:2406.06025](https://arxiv.org/abs/2406.06025); Sahu et al., CodeQueries, [arXiv:2209.08372](https://arxiv.org/abs/2209.08372); Cai et al. 2026, SWE-QA-Pro, [arXiv:2603.16124](https://arxiv.org/abs/2603.16124)
- Tang & Yang 2024, MultiHop-RAG, [arXiv:2401.15391](https://arxiv.org/abs/2401.15391); [code](https://github.com/yixuantt/MultiHop-RAG); [data](https://huggingface.co/datasets/yixuantt/MultiHopRAG)
- Peng et al. 2026, SWE-QA, [arXiv:2509.14635](https://arxiv.org/abs/2509.14635); [code](https://github.com/peng-weihan/SWE-QA-Bench); [data](https://huggingface.co/datasets/swe-qa/SWE-QA-Benchmark)
- Zheng et al. 2023, [arXiv:2306.05685](https://arxiv.org/abs/2306.05685); Panickssery et al. 2024, [arXiv:2404.13076](https://arxiv.org/abs/2404.13076); Wataoka et al. 2024, [arXiv:2410.21819](https://arxiv.org/abs/2410.21819); Li et al. 2025, [arXiv:2502.01534](https://arxiv.org/abs/2502.01534); Thakur et al. 2024, [arXiv:2406.12624](https://arxiv.org/abs/2406.12624)
- Sainz et al. 2023, [arXiv:2310.18018](https://arxiv.org/abs/2310.18018); Golchin & Surdeanu 2023, [arXiv:2308.08493](https://arxiv.org/abs/2308.08493); Liang et al. 2025, [arXiv:2506.12286](https://arxiv.org/abs/2506.12286); Zhang et al. 2025, SWE-bench-Live, [arXiv:2505.23419](https://arxiv.org/abs/2505.23419)
- Anthropic, [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview) (Claude Haiku 5.5 specifications)
