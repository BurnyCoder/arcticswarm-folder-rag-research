# Experiment day1-B: how many agents? Sweep over the swarm's subagent cap

- **Date:** 2026-11-18
- **Status:** completed. This is an exploratory sensitivity analysis (preregistration Amendment 2), run at the user's request after M and B2.
- **Numbers:** all filled from `results/day1/metrics.json`.

## Question and design
What number of agents is best for ArcticSwarm on local-folder RAG with Claude Haiku 5.5?

- **Knob:** `swarm.max_subagents`, the hard cap on spawned subagents. The task queue hands extra tasks to freed workers.
- **Arms:**

  | Arm | Max agents |
  |---|---|
  | `M_cap2` | 2 |
  | `M_cap4` | 4 |
  | `M_cap8` | 8 |
  | `M_cap32` | 32 (added by Amendment 3) |
  | M | 16 (ArcticSwarm default) |
  | B2 | 1 (single agent, no orchestration) |

- **Held fixed:** model, effort, tools, skills, gates, timeouts, and the same 20 question ids.
- **Concurrency:** caps 2/4/8 ran concurrently from 17:01; cap 32 started at 18:42 while caps 2/4 were finishing. Per-call API latency was unchanged by the concurrency, and the only API errors were connection resets when ArcticSwarm's watchdog closed calls at the time limit (§Checks).
- **Pre-specified reading of "optimal":** the cheapest arm whose quality CI overlaps the best arm's. This is descriptive only; there are no significance claims with n=20 per arm.

## Results

{{TABLES}}

![Agent-count sweep](../../results/day1/fig_agent_sweep.png)

| Arm | max agents | agents actually spawned / q | MultiHop-RAG acc. [95% CI] | SWE-QA /100 [95% CI] | $/q | median s |
|---|---|---|---|---|---|---|
| B2 | 1 | 1 | {{summary.B2.mhr_judge_acc|pct}} {{summary.B2.mhr_judge_ci|pctci}} | {{summary.B2.swe_mean|f1}} {{summary.B2.swe_ci|f1ci}} | {{summary.B2.cost_usd_per_q|usd}} | {{summary.B2.latency_s_median|int}} |
| M_cap2 | 2 | {{summary.M_cap2.agents_spawned_mean|f1}} | {{summary.M_cap2.mhr_judge_acc|pct}} {{summary.M_cap2.mhr_judge_ci|pctci}} | {{summary.M_cap2.swe_mean|f1}} {{summary.M_cap2.swe_ci|f1ci}} | {{summary.M_cap2.cost_usd_per_q|usd}} | {{summary.M_cap2.latency_s_median|int}} |
| M_cap4 | 4 | {{summary.M_cap4.agents_spawned_mean|f1}} | {{summary.M_cap4.mhr_judge_acc|pct}} {{summary.M_cap4.mhr_judge_ci|pctci}} | {{summary.M_cap4.swe_mean|f1}} {{summary.M_cap4.swe_ci|f1ci}} | {{summary.M_cap4.cost_usd_per_q|usd}} | {{summary.M_cap4.latency_s_median|int}} |
| M_cap8 | 8 | {{summary.M_cap8.agents_spawned_mean|f1}} | {{summary.M_cap8.mhr_judge_acc|pct}} {{summary.M_cap8.mhr_judge_ci|pctci}} | {{summary.M_cap8.swe_mean|f1}} {{summary.M_cap8.swe_ci|f1ci}} | {{summary.M_cap8.cost_usd_per_q|usd}} | {{summary.M_cap8.latency_s_median|int}} |
| M | 16 | {{summary.M.agents_spawned_mean|f1}} | {{summary.M.mhr_judge_acc|pct}} {{summary.M.mhr_judge_ci|pctci}} | {{summary.M.swe_mean|f1}} {{summary.M.swe_ci|f1ci}} | {{summary.M.cost_usd_per_q|usd}} | {{summary.M.latency_s_median|int}} |
| M_cap32 | 32 | {{summary.M_cap32.agents_spawned_mean|f1}} | {{summary.M_cap32.mhr_judge_acc|pct}} {{summary.M_cap32.mhr_judge_ci|pctci}} | {{summary.M_cap32.swe_mean|f1}} {{summary.M_cap32.swe_ci|f1ci}} | {{summary.M_cap32.cost_usd_per_q|usd}} | {{summary.M_cap32.latency_s_median|int}} |

Paired differences against M (bootstrap 95% CIs; exploratory):

| Arm | MultiHop-RAG accuracy diff vs M [CI] | SWE-QA diff vs M [CI] |
|---|---|---|
| M_cap2 | {{sweep_vs_M.M_cap2.H1.diff|pct}} {{sweep_vs_M.M_cap2.H1.ci|pctci}} | {{sweep_vs_M.M_cap2.H3.diff|f1}} {{sweep_vs_M.M_cap2.H3.ci|f1ci}} |
| M_cap4 | {{sweep_vs_M.M_cap4.H1.diff|pct}} {{sweep_vs_M.M_cap4.H1.ci|pctci}} | {{sweep_vs_M.M_cap4.H3.diff|f1}} {{sweep_vs_M.M_cap4.H3.ci|f1ci}} |
| M_cap8 | {{sweep_vs_M.M_cap8.H1.diff|pct}} {{sweep_vs_M.M_cap8.H1.ci|pctci}} | {{sweep_vs_M.M_cap8.H3.diff|f1}} {{sweep_vs_M.M_cap8.H3.ci|f1ci}} |
| M_cap32 | {{sweep_vs_M.M_cap32.H1.diff|pct}} {{sweep_vs_M.M_cap32.H1.ci|pctci}} | {{sweep_vs_M.M_cap32.H3.diff|f1}} {{sweep_vs_M.M_cap32.H3.ci|f1ci}} |

## Interpretation
SWEEP_INTERPRETATION

## Checks
- All arms used the same question ids and judge.
- Each arm had its own hash-verified sandbox copy of every folder (`/corpus/day1/<arm>/<folder>`).
- API errors per arm are counted from the full LLM-call logs (`logs/llm_calls_day1_<arm>_*.jsonl`).
