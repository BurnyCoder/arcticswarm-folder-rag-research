| Condition | max agents | agents spawned / q | MultiHop-RAG acc. (judge) [95% CI] | EM | official overlap | evidence recall | SWE-QA score /100 [95% CI] | $/question | median latency (s) | tool calls / q | bash+python / q | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Single agent (B2) | 1 | – | 100% [21%, 100%] (n=1) | 0% | 100% | 100% | 40.0 [40.0, 40.0] (n=1) | 0.004 | 19 | 6.5 | 3.0 | 0 |
| Swarm cap 16 (M) | 16 | – | 100% [21%, 100%] (n=1) | 0% | 100% | 100% | 28.0 [28.0, 28.0] (n=1) | 0.247 | 284 | 109.5 | 32.5 | 0 |

T0 trivial baselines on all 2556 MultiHop-RAG queries (no API calls):

| Trivial answer | official word-overlap metric | normalized EM |
|---|---|---|
| majority_per_type | 55.4% | 53.1% |
| constant_hedge | 64.3% | 30.6% |

Pre-registered paired tests (M vs B2, Holm across H1/H3):

| Hypothesis | difference (M − B2) | 95% bootstrap CI | p | p (Holm) | supported |
|---|---|---|---|---|---|
| H1: MultiHop-RAG accuracy | +0% | [0%, 0%] | 1.000 | 1.000 | no |
| H3: SWE-QA score | -12.0 | [-12.0, -12.0] | 1.000 | 1.000 | no |
