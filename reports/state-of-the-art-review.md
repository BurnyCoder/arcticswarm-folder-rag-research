# State of the art: agentic RAG over document collections and codebases

Last updated: 2026-11-18

**Summary.** The best published MultiHop-RAG accuracies are Integration (combining RAG and GraphRAG evidence) at 77.62% with Llama 3.1-70B, test-set size not stated ([Han et al., arXiv v3](https://arxiv.org/html/2502.11371v3)) and QCG-RAG at 79.60% on the first 500 queries ([Wu et al.](https://arxiv.org/html/2509.21237)). The original paper's GPT-4 with retrieved chunks scored 0.56 ([Tang & Yang](https://arxiv.org/html/2401.15391v1)). These numbers come from different generators, test subsets and matching rules, so they cannot be ranked directly. On SWE-QA v2, the best open framework is OpenHands with GPT-5.1 at 70.79/100, with Cursor at 70.66 ([Peng et al. v2](https://arxiv.org/html/2509.14635v2), Table 3). On BrowseComp-Plus, ArcticSwarm reports 88.3% with GPT-5 under a GPT-4.1 judge ([v2](https://arxiv.org/html/2609.01870v2)). The live leaderboard's top self-reported entry is 95.18% under a Qwen3-32B judge ([leaderboard data](https://tevatron-browsecomp-plus.hf.space/data/leaderboard.json)). Coding tools are split: Claude Code reports that agentic grep and file reads beat vector RAG, and Sourcegraph Cody replaced embeddings with BM25-style search. Cursor first reported gains from semantic search and now documents a grep-based setup. As far as we found, no controlled public comparison exists across both document QA and code QA.

Numbers marked **(our computation)** were derived by us from public data on 2026-11-18. See [literature-review.md](literature-review.md) for method details and caveats.

---

## 1. MultiHop-RAG (609 news articles, 2,556 queries)

**Comparability warning.** The official [`qa_evaluate.py`](https://github.com/yixuantt/MultiHop-RAG/blob/main/qa_evaluate.py) counts an answer as correct if it shares any lowercased whitespace token with the gold answer. Under that rule, a constant `"yes no insufficient sam google"` scores **85.6%**, and a per-type constant answer scores 55.4% (53.1% under normalized exact match) (our computation from [HF data](https://huggingface.co/datasets/yixuantt/MultiHopRAG); see [literature review §7.1](literature-review.md)). Papers rarely state which matching rule they used.

| Source (version) | Generator | Retrieval / method | Test set | Metric as stated | Overall | Inference | Comparison | Temporal | Null |
|---|---|---|---|---|---|---|---|---|---|
| [Tang & Yang 2024](https://arxiv.org/html/2401.15391v1), Table 6 | GPT-4 | top-6 retrieved 256-token chunks (≤2,048 tokens) | not stated for this column | "accuracy" (rule not stated) | 0.56 | – | – | – | – |
| same | GPT-4 | ground-truth evidence | non-null queries | same | 0.89 | – | – | – | – |
| same, Table 5 (retrieval only) | – | voyage-02 + bge-reranker-large | non-null | MRR@10 0.586, Hits@10 0.7467 | – | – | – | – | – |
| [Han et al. (KDD '26), v4](https://arxiv.org/html/2502.11371v4), Table 2 | Llama 3.1-8B | vanilla RAG (text-embedding-ada-002, k=10) | not stated | accuracy "following original paper" | 67.02 | 92.16 | 57.59 | 30.70 | 96.01 |
| same | Llama 3.1-8B | HippoRAG2 | not stated | same | 70.27 | 91.54 | 58.41 | 49.91 | 85.71 |
| same | Llama 3.1-8B | Community-GraphRAG (Local) | not stated | same | 69.01 | 86.89 | 60.63 | 50.60 | 80.07 |
| same, Table 5/12 | Llama 3.1-70B | Community-GraphRAG, graph built by GPT-4o | not stated | same | 75.08 | 93.63 | 66.59 | 58.49 | 81.06 |
| [Han et al., v3](https://arxiv.org/html/2502.11371v3), Table 22 | Llama 3.1-70B | "Integration" (RAG + GraphRAG evidence) | not stated | same | **77.62** | 96.45 | 73.48 | 66.72 | 59.47 |
| [Wu et al. 2025 (QCG-RAG)](https://arxiv.org/html/2509.21237), Table 1 | Qwen2.5-72B-Instruct | naive RAG | first 500 queries | "exact-match accuracy" + Qwen2.5-72B judge | 75.80 | 93.46 | 66.85 | 68.00 | 71.21 |
| same | same | LightRAG | first 500 | same | 72.20 | 94.12 | 71.82 | 59.00 | 42.42 |
| same | same | GraphRAG | first 500 | same | 67.20 | 81.05 | 64.09 | 66.00 | 45.45 |
| same | same | **QCG-RAG** | first 500 | same | **79.60** | 93.46 | 74.59 | 69.00 | 77.27 |
| Trivial: per-type constant (our computation) | none | none | all 2,556 | token overlap / exact match | 55.4 / 53.1 | 40.8 / 33.7 | 59.8 / 59.8 | 46.3 / 46.3 | 100 / 100 |

Notes:
- Han et al. (RAG vs GraphRAG) found that token-matched RAG nearly ties GraphRAG with Llama 3.1-70B: 71.01 vs 71.17 ([v4](https://arxiv.org/html/2502.11371v4), Table 15). GraphRAG variants trade lower null-query accuracy for higher temporal and comparison accuracy. Community-GraphRAG (Global) scores 19.27 on null queries with the 8B model.
- Microsoft GraphRAG ([Edge et al., arXiv:2404.16130](https://arxiv.org/abs/2404.16130)) used the MultiHop-RAG *corpus* (1.7M tokens, 3,197 chunks of 600 tokens) for global sense-making questions. It reports LLM-judged win rates of 72–80% for comprehensiveness on News, not accuracy on MultiHop-RAG queries.
- The MultiHop-RAG repository added BM25, hybrid RRF and LangGraph "agentic RAG" scripts on 2026-07-16 (commit "feat: add hybrid and agentic RAG workflows", [repo](https://github.com/yixuantt/MultiHop-RAG)). The README reports no results for them.
- We found **no published agentic or multi-agent result with a frontier LLM on the full MultiHop-RAG under a strict metric** **[absence of evidence, not proof of absence]**.

## 2. SWE-QA (v2: 720 questions, 15 Python repositories; score 0–100)

All values below are from [Peng et al. v2](https://arxiv.org/html/2509.14635v2), Table 3, parsed from the HTML. The judge is Claude Sonnet 4.5, using the 5-dimension rubric with each dimension scored 1–20, and agent iterations are capped at 10.

| Method | Qwen3-Coder-30B-A3B | Qwen3-Coder-480B-A35B | Kimi K2 | GLM-4.6 | Gemini 2.5 Pro | GPT-5.1 |
|---|---|---|---|---|---|---|
| Direct (closed-book) | 50.80 | 54.61 | 51.47 | 56.64 | 54.71 | 61.41 |
| Function-chunk RAG (voyage-code-3, top-5) | 63.40 | 62.96 | 60.08 | 57.46 | 60.02 | 66.57 |
| Sliding-window RAG (100 lines) | 64.86 | 65.39 | 62.44 | 60.72 | 65.68 | 66.79 |
| SWE-agent | 57.44 | 64.00 | 67.72 | 69.85 | 63.76 | 69.20 |
| OpenHands | 65.88 | 68.57 | 66.18 | **70.15** | 65.63 | **70.79** |

Commercial tools: Cursor 70.66 and Tongyi Lingma 69.07.

- **Best reported score per method:** Direct 61.41, function-chunk RAG 66.57, sliding-window RAG 66.79, SWE-agent 69.85, OpenHands 70.79, Cursor 70.66 (all from v2 Table 3).
- **Per question type** (OpenHands, mean over 6 models, Table 4): What 65.81, Why 69.77, Where 66.76, How 69.13. The hardest intentions are Architecture exploration (61.84) and Data/Control-flow (65.05).
- **Per repository** (OpenHands, mean over 6 models, Table 5): the 12 SWE-bench repositories average 68.59, against 64.98 for the 3 SWE-bench-Live repositories. The highest is flask (75.42) and the lowest pylint (62.01).
- **Human evaluation** (Table 7; GPT-5.1 answers, 3 engineers): Direct 66.43 and OpenHands 82.33. The ordering matches the LLM judge, but no agreement statistic is given.
- **Token cost** (Table 8, input/output per question, averaged over models): Direct 94/63, sliding-window RAG 6,302/138, SWE-agent 126,026/4,627, OpenHands 87,045/1,930.
- **v1 (576 questions, 0–50 scale, different judge)** is not comparable. Its best entry was SWE-QA-Agent with Claude 3.7 Sonnet at 47.82/50 ([v1 HTML](https://arxiv.org/html/2509.14635v1), Table 4).
- **Related newer benchmark.** SWE-QA-Pro ([arXiv:2603.16124](https://arxiv.org/abs/2603.16124)) filters out directly answerable questions and uses long-tail repositories. It reports about 13 points of agentic gain over direct answering for Claude Sonnet 4.5. We did not extract its full results tables.

## 3. BrowseComp-Plus (830 queries, ~100K-document fixed corpus) and BrowseComp

### 3.1 Reference results from papers (GPT-4.1 judge)

| Source | System | Retriever | Accuracy |
|---|---|---|---|
| [Chen et al. 2025](https://arxiv.org/html/2508.06600v1) | GPT-5, standard search tool (top-5) | BM25 | 55.90% |
| same | GPT-5 | Qwen3-Embedding-8B | 70.12% |
| same | Sonnet 4 / Opus 4 | BM25 | 14.34% / 15.54% |
| same | Sonnet 4 / Opus 4 | Qwen3-Embedding-8B | 36.75% / 36.14% |
| [ArcticSwarm v2](https://arxiv.org/html/2609.01870v2), Table 1 | ArcticSwarm, GPT-5 | hybrid BM25 + Arctic Embed L v2.0 + reranker | **88.3%** |
| same | ArcticSwarm, Sonnet 4.5 | same | 80.0% |
| same | ArcticSwarm, Qwen 3.5-27B (3 runs) | same | 82.6 ± 0.5% |
| same | MiroFlow, GPT-5 / Sonnet 4.5 / Qwen 3.5-27B | same | 66.0% / 61.0% / 70.6 ± 3.7% |
| same (citing the Claude Opus 4.5 System Card) | Provider deep research, GPT-5 / Sonnet 4.5 | provider's own | 72.9% / 67.2% |

Live-web BrowseComp (1,266 questions): ArcticSwarm scores 73.6% with GPT-5 and 50.2% with Sonnet 4.5. The published scores are 54.9% and 43.8%, and MiroFlow reports 63.4% with GPT-5 ([ArcticSwarm v2](https://arxiv.org/html/2609.01870v2), Table 4). OpenAI Deep Research scored 51.5% at release ([Wei et al.](https://arxiv.org/html/2504.12516)).

### 3.2 Leaderboard (Qwen3-32B judge; self-reported submissions; snapshot of [leaderboard.json](https://tevatron-browsecomp-plus.hf.space/data/leaderboard.json) on 2026-11-18)

| Accuracy | LLM | Retriever | Scaffold (abridged from the entry) | Submitter, date |
|---|---|---|---|---|
| 95.18 | GPT-5 | Hybrid Qwen2-7B + Reason-ModernColBERT | multi-agent, up to 8 agents, `search` + `get_doc`, 209 search calls per query | AI21, 2026-04-28 |
| 90.72 | GLM-5.1-FP8 | Hybrid BM25 + Qwen3-Embed-8B | multi-agent swarm, truncated documents extended on demand | Sail Research, 2026-04-17 |
| 90.48 | GPT-5 | Mixedbread Search v3 | `search` + `get_document` | Mixedbread, 2026-03-19 |
| 90.48 | GPT-5.5 | BM25 + "Question's Gambit" | LLM-expanded first query, then standard search | Hamidi Rad et al., 2026-09-19 |
| 87.11 | GPT-5 | Reason-ModernColBERT | RLM: Python REPL with `search` and `grep_docs` | Neuland AI, 2026-10-23 |
| 71.93 | GPT-6-luna | BM25 | `search` + `get_document` | Marina, 2026-10-04 |
| 57.59 | GPT-5 | BM25 | standard (top-5 snippets) | BrowseComp-Plus, 2025-08-08 |

The table shows three things:
1. Richer tools (full-document fetch, code REPL, query expansion) let BM25-based agents reach 72–90%, against 57.6% for the standard BM25 scaffold.
2. The top entries are multi-agent systems.
3. No Claude 4.5+ or 5.x entry appears on the leaderboard (our reading of the JSON). ArcticSwarm's numbers are not on the leaderboard and use a different judge. The leaderboard states that the two judges differ by less than 1% ([metrics.md](https://huggingface.co/spaces/Tevatron/BrowseComp-Plus/blob/main/public/blobs/metrics.md)).

## 4. Practical "chat with your folder or codebase" systems

| System | Retrieval approach (as documented) | Evidence quality | Source |
|---|---|---|---|
| Claude Code | An agentic loop with file search by pattern and regex, file reads and shell execution. No index is described. | The creator's statement that "agentic search out-performed RAG" in internal testing, with no published benchmark. A 2026 X post says early versions used RAG with a local vector DB ([x.com/bcherny](https://x.com/bcherny/status/2017824286489383315); seen via search-result snippet, not opened) **[post text unverified]**. | [docs](https://code.claude.com/docs/en/how-claude-code-works); [HN, 2025-02-24](https://news.ycombinator.com/item?id=43164253) |
| Cursor | 2025-11-06: semantic search gave "on average 12.5% higher accuracy" (6.5–23.5% depending on model) on an internal benchmark. The current docs say Cursor "does not store embeddings of your codebase for search" and use local Instant Grep plus an Explore subagent. | Vendor self-report; the strategy changed over time. Cursor scores 70.66 on SWE-QA v2. | [blog](https://cursor.com/blog/semsearch); [docs](https://cursor.com/docs/context/semantic-search) |
| Sourcegraph Cody | Replaced embedding retrieval with Sourcegraph's native search, which uses "an adapted form of the BM25 ranking function" plus other signals. Reasons given: privacy, maintenance, scale. | Vendor blog, 2024-02-15; no accuracy numbers | [blog](https://sourcegraph.com/blog/how-cody-understands-your-codebase) |
| aider | A repository map built with tree-sitter, ranked by a graph algorithm over the file-dependency graph, within a token budget (`--map-tokens`, default 1k) | Documentation only | [docs](https://aider.chat/docs/repomap.html); [2023 post](https://aider.chat/2023/10/22/repomap.html) |
| LlamaIndex | `SimpleDirectoryReader` loads a folder (optionally `recursive=True`, filtered by `required_exts`) into Documents for chunking and vector indexing | Library documentation | [docs](https://developers.llamaindex.ai/python/framework/module_guides/loading/simpledirectoryreader/) |
| LangChain | `DirectoryLoader(path, glob="**/[!.]*", loader_cls=UnstructuredFileLoader, recursive=False, use_multithreading=False, ...)` | Source code | [source](https://github.com/langchain-ai/langchain-community/blob/main/libs/community/langchain_community/document_loaders/directory.py) |
| SWE-agent / OpenHands | Shell and file-tool agents run over a checkout | Peer-reviewed; SWE-QA v2 baselines (Section 2) | [SWE-agent](https://arxiv.org/abs/2405.15793); [OpenHands](https://arxiv.org/abs/2407.16741) |
| Code-REPL scaffolds (RLM, Agentica) | The agent writes Python over retrieved documents or the corpus | BrowseComp-Plus leaderboard entries (Section 3.2); [RLM paper](https://arxiv.org/abs/2512.24601) | as cited |

## 5. Gap and what our experiment adds

1. **No controlled cross-domain test of the swarm.** ArcticSwarm's gated-BBS gain (+34.2 points over its single agent and +20.1 over Majority@20 on BrowseComp-Plus) has only been shown for web-style deep research with hard, short-answer questions. It is untested on local-folder RAG with multi-hop news QA or long-form code QA, and untested with a small, fast model (Haiku 5.5) running every role.
2. **No public head-to-head of agentic search and one-shot lexical RAG at a fixed model.** The coding-tool debate (Claude Code, Cursor, Cody) rests on vendor statements and internal benchmarks. SWE-QA compares RAG and agents but caps agents at 10 iterations and uses a same-family judge for Claude agents. Our design holds the model (Haiku 5.5), corpus and BM25 tool fixed and varies only the orchestration: closed-book, random-chunk RAG, BM25 one-shot RAG, single agent, swarm, and swarm without code execution. This isolates that comparison.
3. **Code execution as a retrieval channel.** BrowseComp-Plus leaderboard entries suggest REPL and grep tools compensate for weak retrievers, but none of them ablates code execution while holding everything else fixed. Our no-code-execution ablation does.
4. **Measurement hygiene missing from prior MultiHop-RAG reports.** Prior reports do not include trivial baselines under the official metric (our computation: 55.4% for a per-type constant), a strict-match metric, or contamination controls for a model with a June 2026 training cutoff ([Anthropic](https://platform.claude.com/docs/en/about-claude/models/overview)). We will report all three, together with compute-matched voting baselines and paired bootstrap CIs following ArcticSwarm's protocol.
5. **What we cannot claim.**
   - SWE-QA scores from a different judge are not comparable with v2 Table 3.
   - MultiHop-RAG numbers from other papers use different generators, subsets and matching rules, so they serve as context, not as a leaderboard.
   - A gold-evidence oracle for SWE-QA must be constructed from the reference answers, which leaks answer content. It is therefore a diagnostic upper bound, not a fair condition.
