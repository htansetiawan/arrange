# E2s — chained revision sessions (S1 synthetic, S2 real; 8 turns each; the next turn starts from the arm's own output)

| model | arm | sessions | turns done right | sessions ending exactly on gold | same, not counting the bar-33 beat-map turn (not answerable from the plan) | paths off gold at the end (mean) | composer decisions lost at the end | re-render needs missed | rejected turns | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | ARRANGE typed ops | 6 | 44/48 | 3/6 | 6/6 | 0.5 | 0 | 1 | 0/48 | 0.12 |
| claude-haiku-5-5 | named edits (unchecked) | 6 | 39/48 | 0/6 | 3/6 | 1.5 | 0 | 2 | 0/48 | 0.13 |
| claude-haiku-5-5 | rewrite + ARRANGE notes | 6 | 38/48 | 0/6 | 1/6 | 6.8 | 0 | 2 | 3/48 | 0.32 |
| claude-haiku-5-5 | rewrite, no ARRANGE | 6 | 41/48 | 1/6 | 4/6 | 4.8 | 0 | 0 | 2/48 | 0.32 |
| claude-opus-5-5 | ARRANGE typed ops | 6 | 45/48 | 3/6 | 6/6 | 0.5 | 0 | 0 | 0/48 | 3.97 |
| claude-opus-5-5 | named edits (unchecked) | 6 | 42/48 | 0/6 | 3/6 | 2.2 | 0 | 0 | 0/48 | 4.22 |
| claude-opus-5-5 | rewrite + ARRANGE notes | 6 | 41/48 | 0/6 | 3/6 | 1.5 | 0 | 1 | 0/48 | 12.81 |
| claude-opus-5-5 | rewrite, no ARRANGE | 6 | 40/48 | 0/6 | 3/6 | 2.0 | 0 | 0 | 0/48 | 12.85 |
| claude-sonnet-5-5 | ARRANGE typed ops | 6 | 45/48 | 3/6 | 6/6 | 0.5 | 0 | 0 | 0/48 | 2.55 |
| claude-sonnet-5-5 | named edits (unchecked) | 6 | 38/48 | 0/6 | 0/6 | 2.7 | 0 | 0 | 1/48 | 1.87 |
| claude-sonnet-5-5 | rewrite + ARRANGE notes | 6 | 30/48 | 0/6 | 0/6 | 40.5 | 13 | 1 | 1/48 | 4.82 |
| claude-sonnet-5-5 | rewrite, no ARRANGE | 6 | 25/48 | 0/6 | 0/6 | 78.5 | 26 | 3 | 2/48 | 3.96 |
| gemma-4-31b-fp8 | ARRANGE typed ops | 6 | 45/48 | 3/6 | 6/6 | 0.5 | 0 | 0 | 0/48 | 0.00 |
| gemma-4-31b-fp8 | named edits (unchecked) | 6 | 36/48 | 0/6 | 0/6 | 2.0 | 0 | 6 | 0/48 | 0.00 |
| gemma-4-31b-fp8 | rewrite + ARRANGE notes | 6 | 39/48 | 3/6 | 3/6 | 2.7 | 4 | 0 | 5/48 | 0.00 |
| gemma-4-31b-fp8 | rewrite, no ARRANGE | 6 | 23/48 | 0/6 | 0/6 | 5.7 | 6 | 3 | 9/48 | 0.00 |
| qwen3.5-27b-fp8 | ARRANGE typed ops | 6 | 45/48 | 3/6 | 6/6 | 0.5 | 0 | 0 | 0/48 | 0.00 |
| qwen3.5-27b-fp8 | named edits (unchecked) | 6 | 39/48 | 0/6 | 2/6 | 2.2 | 0 | 1 | 2/48 | 0.00 |
| qwen3.5-27b-fp8 | rewrite + ARRANGE notes | 6 | 42/48 | 2/6 | 4/6 | 1.3 | 0 | 0 | 1/48 | 0.00 |
| qwen3.5-27b-fp8 | rewrite, no ARRANGE | 6 | 31/48 | 0/6 | 0/6 | 5.8 | 2 | 1 | 4/48 | 0.00 |

S2 turn 5 asks to move bar 33's downbeat half a second earlier; the plan does not contain bar 33's time (the beat map is not in the prompt), so no arm can hit it except by luck; asking is the reasonable answer. It costs every arm equally.
