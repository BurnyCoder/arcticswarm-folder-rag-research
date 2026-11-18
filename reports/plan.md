# Plan and progress log

Last updated: 2026-11-18

## Goal
Install and run [ArcticSwarm](https://github.com/Snowflake-AI-Research/ArcticSwarm) and adapt it from web research to retrieval-augmented generation over local folders with many files. There is no web research, every agent runs on Claude Haiku 5.5 (`claude-haiku-5-5`), and agents may run arbitrary bash/Python and install any tool. The adaptation is evaluated with the pre-registered design in [preregistration.md](preregistration.md).

## Constraints from the user
- Day 1 (2026-11-18):
  - Run only the **main method (M) once** and **one baseline (B2, single agent) once**, except for fixing issues.
  - Spend **at most $50**.
  - All other experiments (B1, C1, C2, O, B3, A1) are postponed.
- Run order: main method → baselines → ablations.
- The GitHub repositories and the Hugging Face collection are **private**.

## Repositories
- Harness and reports: `BurnyCoder/arcticswarm-folder-rag-research` (private), this repo.
- Adapted framework: `BurnyCoder/ArcticSwarm-folder-rag` (private), branch `folder-rag`, a git submodule at `./ArcticSwarm`.

## Work plan
1. [x] Set up the project: uv, Python 3.12, dependencies pinned to ArcticSwarm's validated versions, private repos.
2. [x] Literature and state-of-the-art review: [literature-review.md](literature-review.md), [state-of-the-art-review.md](state-of-the-art-review.md).
3. [x] Preregistration: [preregistration.md](preregistration.md).
4. [x] Haiku 5.5 API probe (`scripts/probe_haiku.py`). Findings:
   - `budget_tokens` thinking and `temperature` both return a 400.
   - An `anthropic-workspace-id` header is required.
   - Adaptive thinking, tool loops, edited history and synthetic tool turns are all accepted; the history-editing check is not enforced on this account.
5. [ ] Fork patches:
   - [x] Windows compatibility.
   - [x] Haiku 5.5 support.
   - [x] Fix that keeps the Anthropic key away from OpenAI.
   - [ ] Folder backend.
   - [ ] WSL sandbox exec.
   - [ ] Prompts and skills.
   - [ ] LLM call log.
   - [ ] Tests.
6. [ ] Harness: dataset builders, run wrapper, judge, analysis, CLI.
7. [ ] Smoke test (≤3 questions per dataset per condition) and cost check. N fixed by the user at 20 per condition (10 MultiHop-RAG + 10 SWE-QA; preregistration Amendment 1).
8. [ ] Run M (swarm) on MultiHop-RAG, then SWE-QA. Judge, analyze, push.
9. [ ] Run B2 (single agent) on the same ids. Judge, analyze, push.
10. [ ] Reports, paper, README, results site. Fact-check.
11. Later days: B1, C1, C2, O, B3 (compute-matched voting), A1 (no code execution), plus a repeat run for variance.

## Decisions and why
- **Model `claude-haiku-5-5`.** "Haiku" with no version means the current generation (Anthropic model table). Haiku 4.5 still works through the budget-thinking path.
- **Dependency pins.** An unpinned install pulled anthropic 2.x, openai 3.x and mcp 2.x, which are untested major versions. The project pins to ArcticSwarm's `requirements.txt` versions instead.
- **Private copy instead of a fork.** GitHub forks of public repos cannot be private, so `ArcticSwarm-folder-rag` is a private copy. The public fork `BurnyCoder/ArcticSwarm` was created before the privacy request and is unused.
- **WSL sandbox instead of Git Bash.** The user asked that agents be able to use any bash tool and install any Python library. Docker is not installed. A dedicated WSL distro gives root plus apt/pip while isolating the host.
- **The "browsing" profile name and the `web_search` / `web_fetch` tool names are kept.** ArcticSwarm's review gates and builder-reviewer classification are keyed on them. Descriptions and system prompts say "local folder".
- **MultiHop-RAG scoring changed from the official word-overlap metric.** A constant hedge string scores 85.6% under it (literature review). Scoring uses a strict judge on a forced `FINAL ANSWER:` line, plus normalized exact match.
