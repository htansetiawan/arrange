# E2-lyrics rescored (rescore.py; 9 items)

accepted = edit matches his fix or an answer the record accepts; + question = also a question where the request did not pin down one edit (typed arm only: only it has an ask operation). old = the first scoring, same 9 items.

| model | arm | old | accepted | + question (typed) | fitting | phoneme | words | invalid |
|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | bare | 0.04 | 0.26 | - | 7/15 | 0/9 | 0/3 | 0 |
| claude-haiku-5-5 | free | 0.22 | 0.41 | - | 5/15 | 6/9 | 0/3 | 0 |
| claude-haiku-5-5 | typed | 0.33 | 0.56 | 0.67 | 6/15 | 9/9 | 0/3 | 0 |
| claude-opus-5-5 | bare | 0.00 | 0.41 | - | 8/15 | 0/9 | 3/3 | 0 |
| claude-opus-5-5 | free | 0.26 | 0.74 | - | 11/15 | 6/9 | 3/3 | 0 |
| claude-opus-5-5 | typed | 0.30 | 0.56 | 0.74 | 9/15 | 6/9 | 0/3 | 0 |
| claude-sonnet-5-5 | bare | 0.00 | 0.33 | - | 6/15 | 0/9 | 3/3 | 0 |
| claude-sonnet-5-5 | free | 0.33 | 0.67 | - | 8/15 | 7/9 | 3/3 | 0 |
| claude-sonnet-5-5 | typed | 0.52 | 0.59 | 0.67 | 7/15 | 8/9 | 1/3 | 0 |
| gemma-4-31b-fp8 | bare | 0.00 | 0.00 | - | 0/15 | 0/9 | 0/3 | 0 |
| gemma-4-31b-fp8 | free | 0.07 | 0.07 | - | 0/15 | 2/9 | 0/3 | 0 |
| gemma-4-31b-fp8 | typed | 0.22 | 0.30 | 0.41 | 0/15 | 6/9 | 2/3 | 0 |
| qwen3.5-27b-fp8 | bare | 0.00 | 0.07 | - | 1/15 | 0/9 | 1/3 | 0 |
| qwen3.5-27b-fp8 | free | 0.15 | 0.26 | - | 2/15 | 3/9 | 2/3 | 1 |
| qwen3.5-27b-fp8 | typed | 0.19 | 0.19 | 0.30 | 0/15 | 5/9 | 0/3 | 1 |

## Per item, Claude typed (Haiku + Sonnet + Opus, 9 tries): old / accepted / + question

| item | cat | request pinned one edit? | old | accepted | + question |
|---|---|---|---|---|---|
| cp-bar18-assign | fitting | no | 0/9 | 0/9 | 4/9 |
| cp-redbrick-melisma | fitting | no | 0/9 | 1/9 | 2/9 |
| cp-layer-words | words | no | 0/9 | 1/9 | 5/9 |
| cp-layer-pitches | fitting | yes | 5/9 | 9/9 | 9/9 |
| cp-morning-sounds | phoneme | yes | 8/9 | 8/9 | 8/9 |
| cp-footsteps-sounds | phoneme | no | 6/9 | 6/9 | 6/9 |
| cp-waking-sounds | phoneme | yes | 9/9 | 9/9 | 9/9 |
| sd-grace-fold | fitting | no | 1/9 | 7/9 | 7/9 |
| sd-hall-g4 | fitting | no | 2/9 | 5/9 | 6/9 |
