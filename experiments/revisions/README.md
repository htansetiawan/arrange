# Plan revisions

Paper: Section 5.1, "Typed revisions keep earlier decisions", "Across models, and with no ARRANGE at all" and "Over a
session", and the revision figures in the abstract.

A plan the agent edits must change what the composer asked and nothing else. 16 plain-language revision requests are
frozen with the change each one expects: 7 on the real plan of the author's piece (`real/`) and 9 on a synthetic plan
(`synthetic/`). Each model answers every request three times in each arm:

| Arm | The model gets | It answers with |
|---|---|---|
| `typed` | the plan, ARRANGE's notes on the plan's structure, the edit vocabulary | a list of edits, applied by `skills/arrange-plan/scripts/arrangement.py` |
| `patch` | the same | paths and values to set |
| `free` | the same | the whole plan, rewritten |
| `bare` | the plan and a one-line instruction, none of ARRANGE's notes | the whole plan, rewritten |

Scoring compares the changed paths with the expected change: recall and precision of the intended change, unrelated
fields changed, composer decisions overwritten (protected fields), stale layers, and whether a vague or impossible
request was asked about. Sessions chain 8 requests (`sessions.json`), each turn starting from the arm's own previous
output, on one real and one synthetic plan.

## Reproduce the paper's numbers from the stored results

No model is called. `table_models.py` needs SciPy (Wilcoxon test); the rest is the standard library.

```
python3 summarize.py results/summary.json -o results/SUMMARY.md        # the Sonnet table, and the vague requests
python3 split_by_fixture.py results/summary.json
python3 summarize.py results/summary-real.json -o results/SUMMARY-real.md   # "on the real plan alone"
python3 table_models.py                                                 # five models x four arms, Wilcoxon p
python3 table_sessions.py                                               # sessions: fields off, decisions lost
python3 brass_turn.py sessions-results                                  # "put the brass back in"
```

The first table in the paper is from the first Sonnet run (`results/`, three arms). The Sonnet row of the five-model
table is a later re-run with all four arms (`results-models/claude-sonnet-5-5/`); the other models are in the same
folder.

## Notes on the stored results

- Rewritten plans (`free`, `bare`) are stored cut to their first 4,000 characters (3,000 in sessions), so those arms can
  be checked from their stored scores but not re-scored from the text. The `typed` and `patch` answers are complete and
  re-score to the stored values.
- 9 Qwen draws and 5 Qwen session turns reached the 32,000-token limit while reasoning and returned no answer; they are
  scored invalid.
- The published real plan has its local file paths replaced with paths relative to the project, and the agent's name
  replaced with "the agent" in three notes. The runs used the original plan, so the prompts differed from the
  published plan in those strings only. The same replacements are applied to the stored answers. Session ids are
  removed. `FROZEN.sha256` hashes the published inputs.

## Rerun

Write to a new folder so the stored results are not merged with yours:

```
python3 run_e2.py --model claude-sonnet-5-5 --draws 3 --out results-new --arms typed patch free bare
python3 run_sessions.py --model claude-sonnet-5-5 --draws 3 --out sessions-new
```

Claude models are called through the Claude Code CLI (`claude -p`) with no tools, from an empty temporary folder, one
completion per call. Open models are called through any OpenAI-compatible server with `--base-url`. The paper used vLLM
with FP8 weights (`Qwen/Qwen3.5-27B-FP8`, `RedHatAI/gemma-4-31B-it-FP8-block`), each with its own default sampling:

```
vllm serve Qwen/Qwen3.5-27B-FP8 --served-model-name qwen3.5-27b-fp8 --max-model-len 40960 --reasoning-parser qwen3 --port 8011
python3 run_e2.py --model qwen3.5-27b-fp8 --base-url http://localhost:8011/v1 --draws 3 --out results-new
```
