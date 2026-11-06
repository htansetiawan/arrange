# The composer's own corrections

Paper: Section 5.1, "The composer's own corrections".

The composer's real corrections to sung lines (pronunciation, timing, which syllable sits on which note, words) were
frozen as requests, each scored against the fix he made or an equivalent his record accepts. This repository holds the
9 requests that were run on the distributed songs. Most of them (6 of 9) do not pin down a single edit: they describe
what he heard or rely on what he saw on the canvas or had said earlier. None of the 9 is a timing correction, so the
timing lines of the paper's breakdown by category have no counterpart here.

| Arm | The model gets | It answers with |
|---|---|---|
| `typed` | the lyric skill's notes, the fit as a table, the sounds each syllable is sung with, the edit list | edits by row, or a question |
| `free` | the same information | the whole fit, rows rewritten |
| `bare` | the raw rows only | the whole fit, rows rewritten |

Phoneme corrections are scored on the sounds the singer receives, so any edit that produces the right sounds counts.

## Reproduce the paper's numbers from the stored results

```
python3 paper_numbers.py
```

prints every number in the paragraph: rates per model and arm, with and without justified questions; the paired sign
tests over items and models; unrelated rows changed per try; results by category. No model is called. Without the fits
it reads `rescored-draws.json`, the per-try outcomes it wrote when run with the fits. `RESCORE.md` (from `rescore.py`,
which also falls back to `rescored-draws.json`) and `TABLE.md` (the first scoring, from `run_lyrics.py --table`) are
stored outputs, both regenerated on the 9 distributed items.

## Songs not distributed

The paper's numbers for this section were computed with data from two further songs, which the author chose not to
distribute. `paper_numbers.py` on this repository prints the numbers for the distributed songs. They differ as follows
(only the words category, all of it on distributed songs, is the same):

| Number | Paper | This repository |
|---|---|---|
| Requests run; scored after the diagnosis | 17; 15 | 9; 9 |
| Requests that do not pin down one edit | 11 of 15 | 6 of 9 |
| Answers whose whole-fit text is withheld | 459 of 765 | 269 of 405 |
| Tries per model and arm | 45 | 27 |
| Accepted, typed (+ question): Haiku, Opus, Sonnet | 0.47 (0.69), 0.42 (0.58), 0.44 (0.53) | 0.56 (0.67), 0.56 (0.74), 0.59 (0.67) |
| Accepted, free: Haiku, Opus, Sonnet | 0.31, 0.56, 0.51 | 0.41, 0.74, 0.67 |
| Accepted, bare: Haiku, Opus, Sonnet | 0.18, 0.31, 0.27 | 0.26, 0.41, 0.33 |
| Accepted, typed (+ question): Gemma 4 31B, Qwen 3.5 27B | 0.18 (0.24), 0.11 (0.20) | 0.30 (0.41), 0.19 (0.30) |
| Accepted, free / bare: Gemma 4 31B, Qwen 3.5 27B | 0.04 / 0.00, 0.16 / 0.07 | 0.07 / 0.00, 0.26 / 0.07 |
| Typed vs bare, Claude (better / worse / tied, sign test) | 17 / 7 / 21, p = 0.064 | 12 / 6 / 9, p = 0.24 |
| Free vs bare | 16 / 4 / 25, p = 0.012 | 10 / 3 / 14, p = 0.092 |
| Typed vs free | 6 / 8 / 31, p = 0.79 | 4 / 6 / 17, p = 0.75 |
| Unrelated rows changed per try, typed / free / bare: Haiku | 0.51 / 0.38 / 1.16 | 0.67 / 0.48 / 0.85 |
| Opus | 0.31 / 0.31 / 0.73 | 0.44 / 0.41 / 1.19 |
| Sonnet | 0.31 / 0.40 / 0.62 | 0.44 / 0.63 / 1.04 |
| Gemma 4 31B | 4.53 / 0.71 / 15.67 | 1.37 / 1.19 / 2.96 |
| Qwen 3.5 27B | 16.33 / 0.98 / 13.16 | 2.00 / 1.63 / 2.07 |
| Claude by category, typed / free / bare: timing | 11/27, 9/27, 4/27 | none run |
| fitting | 22/63, 24/63, 24/63 | 22/45, 24/45, 21/45 |
| phoneme | 26/36, 23/36, 0/36 | 23/27, 19/27, 0/27 |
| words | 1/9, 6/9, 6/9 | 1/9, 6/9, 6/9 |
| Open models by category: timing | 0/18, 0/18, 1/18 | none run |
| fitting | 0/42, 2/42, 1/42 | 0/30, 2/30, 1/30 |
| phoneme | 11/24, 5/24, 0/24 | 11/18, 5/18, 0/18 |
| words | 2/6, 2/6, 1/6 | 2/6, 2/6, 1/6 |
| Invalid answers, typed / free / bare: Sonnet | 0 / 1 / 0 | 0 / 0 / 0 |
| Gemma 4 31B | 3 / 18 / 0 | 0 / 0 / 0 |
| Qwen 3.5 27B | 2 / 19 / 2 | 1 / 1 / 0 |

## Rerun

With the items in `items/<id>/` (request, fit before and after, pronounce files, the song's beat map):

```
python3 run_lyrics.py --selftest          # every gold fix scores correct
python3 run_lyrics.py --model claude-sonnet-5-5 --draws 3
python3 rescore.py                        # -> RESCORE.md
python3 paper_numbers.py                  # rescored from the answers; rewrites rescored-draws.json
```

Model calls use the backends in `experiments/revisions/run_e2.py` (the Claude Code CLI, or an OpenAI-compatible server
with `--base-url`). `ARRANGE_G2P_PY` points at a Python with `g2p_en` for the sounds step.
