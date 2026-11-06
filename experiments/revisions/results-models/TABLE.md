# T1 — ARRANGE across models (E2, 16 frozen requests x 3 draws)

| model | arm | correct (95% CI) | collateral / draw | overwrote composer | invalid | cost $ |
|---|---|---|---|---|---|---|
| claude-sonnet-5-5 (31 Oct) | with ARRANGE (typed ops) | 0.96 (0.90-1.00) | 0.0 | 0 | 0/48 | 1.01 |
| claude-sonnet-5-5 (31 Oct) | with ARRANGE (patch) | 0.77 (0.65-0.88) | 0.4 | 6 | 1/48 | 1.16 |
| claude-sonnet-5-5 (31 Oct) | ARRANGE notes, free rewrite | 0.38 (0.25-0.52) | 30.2 | 75 | 11/48 | 2.85 |
| claude-haiku-5-5 | with ARRANGE (typed ops) | 0.83 (0.73-0.94) | 0.6 | 0 | 0/48 | 0.07 |
| claude-haiku-5-5 | with ARRANGE (patch) | 0.75 (0.62-0.88) | 0.1 | 0 | 0/48 | 0.08 |
| claude-haiku-5-5 | ARRANGE notes, free rewrite | 0.73 (0.60-0.85) | 0.1 | 0 | 3/48 | 0.24 |
| claude-haiku-5-5 | no ARRANGE at all (bare rewrite) | 0.62 (0.48-0.75) | 1.6 | 2 | 3/48 | 0.24 |
| claude-opus-5-5 | with ARRANGE (typed ops) | 0.90 (0.79-0.98) | 0.0 | 0 | 0/48 | 2.29 |
| claude-opus-5-5 | with ARRANGE (patch) | 0.73 (0.60-0.85) | 0.2 | 0 | 0/48 | 2.59 |
| claude-opus-5-5 | ARRANGE notes, free rewrite | 0.71 (0.56-0.83) | 0.2 | 0 | 0/48 | 8.62 |
| claude-opus-5-5 | no ARRANGE at all (bare rewrite) | 0.69 (0.56-0.81) | 0.7 | 0 | 0/48 | 8.88 |
| claude-sonnet-5-5 | with ARRANGE (typed ops) | 0.98 (0.94-1.00) | 0.0 | 0 | 0/48 | 1.15 |
| claude-sonnet-5-5 | with ARRANGE (patch) | 0.81 (0.69-0.92) | 0.1 | 0 | 0/48 | 1.22 |
| claude-sonnet-5-5 | ARRANGE notes, free rewrite | 0.38 (0.25-0.52) | 19.9 | 48 | 11/48 | 3.07 |
| claude-sonnet-5-5 | no ARRANGE at all (bare rewrite) | 0.33 (0.21-0.46) | 22.1 | 47 | 14/48 | 3.06 |
| gemma-4-31b-fp8 | with ARRANGE (typed ops) | 0.90 (0.81-0.98) | 0.0 | 0 | 1/48 | 0.00 |
| gemma-4-31b-fp8 | with ARRANGE (patch) | 0.67 (0.54-0.79) | 0.4 | 3 | 0/48 | 0.00 |
| gemma-4-31b-fp8 | ARRANGE notes, free rewrite | 0.62 (0.48-0.77) | 2.5 | 4 | 8/48 | 0.00 |
| gemma-4-31b-fp8 | no ARRANGE at all (bare rewrite) | 0.46 (0.33-0.58) | 2.0 | 4 | 8/48 | 0.00 |
| qwen3.5-27b-fp8 | with ARRANGE (typed ops) | 0.83 (0.73-0.94) | 1.9 | 2 | 1/48 | 0.00 |
| qwen3.5-27b-fp8 | with ARRANGE (patch) | 0.69 (0.54-0.81) | 0.2 | 4 | 3/48 | 0.00 |
| qwen3.5-27b-fp8 | ARRANGE notes, free rewrite | 0.71 (0.58-0.83) | 0.4 | 3 | 2/48 | 0.00 |
| qwen3.5-27b-fp8 | no ARRANGE at all (bare rewrite) | 0.50 (0.35-0.65) | 2.2 | 12 | 3/48 | 0.00 |

Paired by request (typed vs free rewrite with ARRANGE notes, and vs bare rewrite with no ARRANGE):
- claude-sonnet-5-5 (31 Oct): typed − free = +0.58 per request (better on 10, worse on 0, same on 6 of 16), Wilcoxon p = 0.002
- claude-haiku-5-5: typed − free = +0.10 per request (better on 5, worse on 3, same on 8 of 16), Wilcoxon p = 0.266
- claude-haiku-5-5: typed − bare = +0.21 per request (better on 7, worse on 1, same on 8 of 16), Wilcoxon p = 0.047
- claude-opus-5-5: typed − free = +0.19 per request (better on 4, worse on 0, same on 12 of 16), Wilcoxon p = 0.125
- claude-opus-5-5: typed − bare = +0.21 per request (better on 6, worse on 0, same on 10 of 16), Wilcoxon p = 0.031
- claude-sonnet-5-5: typed − free = +0.60 per request (better on 10, worse on 0, same on 6 of 16), Wilcoxon p = 0.002
- claude-sonnet-5-5: typed − bare = +0.65 per request (better on 11, worse on 0, same on 5 of 16), Wilcoxon p = 0.001
- gemma-4-31b-fp8: typed − free = +0.27 per request (better on 5, worse on 0, same on 11 of 16), Wilcoxon p = 0.062
- gemma-4-31b-fp8: typed − bare = +0.44 per request (better on 10, worse on 1, same on 5 of 16), Wilcoxon p = 0.009
- qwen3.5-27b-fp8: typed − free = +0.12 per request (better on 5, worse on 2, same on 9 of 16), Wilcoxon p = 0.266
- qwen3.5-27b-fp8: typed − bare = +0.33 per request (better on 8, worse on 1, same on 7 of 16), Wilcoxon p = 0.078
