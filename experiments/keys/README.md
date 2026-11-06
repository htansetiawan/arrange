# Choosing the key

Paper: Section 5.5, "Choosing the key: a rule proposes, the ear decides", and Figure 3.

A copied voice sounds like its singer only where that singer sings. The skill measures the singer's pitch and the
song's notes and turns them into a key with four rules (`skills/arrange-lyrics/scripts/center.py`). The key is the
number of semitones the voice sings above or below the written melody.

| Rule | What it lines up |
|---|---|
| Top note | The song's highest note on the singer's 90th-percentile note |
| Top | The song's 90th-percentile note at or below the singer's, as close to Median as allowed |
| Median | The song's median note on the singer's median note |
| Clip | The song's median note on the reference clip's median note |

Eight copied voices (SoulX-Singer, zero-shot from a reference clip) sang the same 15 seconds of *All the Things You
Are* (48.8 to 63.8 s, around its highest note, D5) at keys two semitones apart, voice only and loudness-matched. For
each clip the composer tagged the register (too low, about right, too high) and rated strain on the top note from 0 to
100. He heard 185 clips in three rounds:

| Round | Folder | Clips | Layout |
|---|---|---|---|
| Pilot ladder | `pilot/` | 48 | Six keys per voice, low to high, the Median rule's key always on rung 4 |
| Blind test | `blind/` | 60 | One clip at a time, shuffled, no names, 6 hidden repeats; predictions frozen in `blind/prereg.json` |
| Recheck | `recheck/` | 14 | The blind round's anomalies, blind again |
| Side by side | `side-by-side/` | 63 | Each voice's 7 to 8 lowest keys stacked, voices anonymous; the composer's picks here are the reference |

`groban-recheck/` holds the key of a named recheck of Groban on the side-by-side clips (7 clips, not counted in the
185). Its answers were not stored.

The percentile in Top note (90th) was chosen on the pilot, leaving one voice out at a time, and frozen before the
blind round. `llm/` holds the language-model key picks: five text models in four conditions (the singer's name; the
name plus the skill's measured percentiles; the numbers with the name hidden; a picture of the singer's notes over
the song's), three draws each, and two audio models that hear a 30-second clip of the singer.

## Reproduce the paper's numbers

No model, audio or network is needed. Python 3 with NumPy; `analyze_posthoc.py` and `analyze_side_by_side.py` also
need SciPy, and `make_fig3.py` needs Matplotlib for the image.

```
python3 paper_numbers.py          # every number in Section 5.5 and the Figure 3 data, from the stored files
python3 make_fig3.py              # figures/fig3.png, figures/fig3.svg, figures/fig3.csv
python3 make_fig3.py --print      # the Figure 3 data only
```

The analyses below are the ones run during the study. They write the tables and joined files that are stored next to
them. Run them in this order, since each reads the previous one's joined file:

```
python3 pilot/analyze_pilot.py               # pilot/RESULT.md, pilot/pilot-joined.json
python3 blind/analyze_blind.py               # blind/RESULT.md (the frozen hypotheses), blind/blind-joined.json
python3 blind/analyze_posthoc.py             # blind/RESULT-posthoc.md (sign test, strain at each rule's key)
python3 recheck/join_recheck.py              # recheck/recheck-joined.json
python3 side-by-side/analyze_side_by_side.py # side-by-side/RESULT.md, side-by-side/side-by-side-joined.json
python3 llm/run_center.py --table            # llm/TABLE.md (models against the composer's sighted keys)
python3 llm/run_listen.py --table            # llm/LISTEN-TABLE.md (audio models)
```

| Paper | Value | Command | Where in the output |
|---|---|---|---|
| First keys by ear lower than the Median rule | 5 of 6 | `paper_numbers.py` | `[5.5]` first line |
| Top note within 1.5 semitones on average, no lean | 1.50, +0.00 | `paper_numbers.py` | `[5.5 rules]` |
| Median 6 too high for every voice | +6.00, 8 of 8 | `paper_numbers.py` | `[5.5]`, `[5.5 rules]` |
| LLMs 4 to 7 too high | 4.0 to 7.4 | `paper_numbers.py` | `[5.5]` LLMs line |
| For Groban only the clip was available | | `paper_numbers.py` | `[5.5]` source line; `data/profiles.json` |
| 185 clips in three rounds | 48 + 60 + 14 + 63 | `paper_numbers.py` | `[5.5]` clips line |
| Pilot: lowest key was the sweet spot for 6 of 8; rule always on the same rung | 6 of 8; rung 4 | `paper_numbers.py`, `pilot/analyze_pilot.py` | `[5.5 pilot]`; `pilot/RESULT.md` |
| Percentile chosen leaving one voice out | 90 in 6 of 8 folds | `paper_numbers.py`, `pilot/analyze_pilot.py` | `[5.5 pilot]`; last bullet of `pilot/RESULT.md` |
| Predictions frozen before listening | | `paper_numbers.py` | `frozen_at` against the first answer |
| Top note: exact for 4 of 8, within 2 for 5 | 4, 5 | `paper_numbers.py` | `[5.5 rules]` |
| Top 3.0; Median and Clip 6.0, too high on average | 3.00 (+2.75); 6.00 (+6.00); 6.00 (+6.00) | `paper_numbers.py` | `[5.5 rules]` |
| Blind round: Top note closer than Median for all 8 (one-sided sign test p = 0.004) | 8 of 8, p = 0.0039 | `paper_numbers.py`, `blind/analyze_posthoc.py` | `[5.5 rules]`; "H1 by direction" in `blind/RESULT-posthoc.md` |
| Strain 67 at Top note's keys against 82 at Median's | 67.0, 81.9 | `paper_numbers.py`, `blind/analyze_posthoc.py` | `[5.5 rules]`; "mean strain" lines in `RESULT-posthoc.md` |
| Top closest for Groban and Bublé, Clip for Jackson | | `paper_numbers.py` | `[5.5 rules]` |
| Reference between Top note and Top, ends included | 5 of 8 | `paper_numbers.py` | `[5.5 rules]` |
| Side by side within 2 of the pilot for all 8 | 8 of 8 | `paper_numbers.py`, `side-by-side/analyze_side_by_side.py` | `[5.5 layout]`; "Agreement" in `side-by-side/RESULT.md` |
| Blind round put 5 voices 2 to 4 semitones lower | 5 voices | `paper_numbers.py` | `[5.5 layout]` |
| Same 52 files: 7 points less strained side by side, same tag in 33 of 52 | -6.9; 33 | `paper_numbers.py`, `side-by-side/analyze_side_by_side.py` | `[5.5 layout]`; "Same audio, two layouts" |
| Repeats moved about 9 points; 5 of 6 kept their tag | 9.0; 5 of 6 | `paper_numbers.py`, `blind/analyze_blind.py` | `[5.5 layout]`; "H3" in `blind/RESULT.md` |
| Two renders strained alone, pitch correct | Clarkson -4, Groban -8 | `paper_numbers.py` | `[5.5 layout]` |
| Sweet spot on the fourth rung for 6 of 8 | 6 of 8 | `paper_numbers.py`, `side-by-side/analyze_side_by_side.py` | `[5.5 layout]` |
| In every layout Median or Clip highest, Top note closest | | `paper_numbers.py` | `[5.5 layout]`, three layouts |
| Claude 4.2 to 5.7; Gemma 4 31B 5.4 to 7.4; Qwen 3.5 27B 4.0 to 5.1; always too high | | `paper_numbers.py` | `[5.5 LLMs]` |
| Gemma 4 E4B 4.7; Qwen2.5-Omni 7B 6.6 (hearing the recording) | | `paper_numbers.py` | `[5.5 LLMs]` |
| Top note 1.3 on the same six | 1.33 | `paper_numbers.py` | `[5.5 LLMs]` |
| Against the sighted keys: Claude 1.8 to 2.0 against 2.9 to 3.6; open models 2.1 to 3.0 against 3.6 to 4.8 | | `paper_numbers.py`, `llm/run_center.py --table` | `[5.5 LLMs]`; `llm/TABLE.md` |
| Top note misses: Jackson and Bolton +3, Groban -4 | | `paper_numbers.py`, `make_fig3.py --print` | `[5.5 why]`; Figure 3 data |
| Figure 3 | | `make_fig3.py` | `figures/fig3.png`, `fig3.svg`, `fig3.csv` |

## Songs not distributed

The paper's sighted-key comparison was computed with one more case, a voice keyed on a song that the author chose not
to distribute. Its prompts, model answers and rule keys are left out here (one of nine cases; 4 prompts, 12 answers per
text model, 3 key answers per audio model). `paper_numbers.py` on this repository prints the numbers for the
distributed songs. Every other number of the section and Figure 3 is the same; these differ:

| Number | Paper | This repository |
|---|---|---|
| Sighted keys the models are compared against | 9 cases on three songs | 8 cases on two songs |
| Claude, mean miss with the measurement (numbers, anon) | 1.8 to 2.0 | 1.6 to 1.8 |
| Claude, mean miss by name | 2.9 to 3.6 | 2.4 to 3.0 |
| Open text models, with the measurement | 2.1 to 3.0 | 2.1 to 2.5 |
| Open text models, by name | 3.6 to 4.8 | 2.9 to 3.9 |

`llm/TABLE.md` and `llm/LISTEN-TABLE.md` were regenerated on the 8 cases; the key columns of both differ from the
versions computed with nine.

Notes on the definitions:

- The reference is the side-by-side pick. Errors are the rule's key minus the reference; positive means too high.
- The blind sweet spot of a voice is the key where the mean strain crosses 50, linear between keys. For a voice whose
  strain is above 50 at every key heard, the sweet spot lies below the lowest key; the sign test then counts Top note
  as closer when its key is lower than Median's. The frozen hypothesis H1 (mean miss to the strain-50 key, on the 5
  voices with a crossing: Top note 2.4 against Median 5.9) is in `blind/RESULT.md`; the sign test and the strain
  comparison were added after it and are in `blind/RESULT-posthoc.md`.
- "Kept their tag" counts a file when the side-by-side tag equals every blind answer for that file (19 files were
  heard more than once blind). Counting a match with at least one blind answer gives 39 of 52.
- "Strain at a rule's key" reads the composer's mean blind strain at that key, linear between the keys he heard and
  the end value beyond them.
- The LLM ranges are mean misses per model and condition on the six voices that the composer also keyed by ear on the
  canvas, against the side-by-side reference. Against the sighted canvas keys (`gold` in the results; eight cases on
  two songs in this repository) the "numbers" and "anon" conditions are the measurement, "name" is the name only.
- In `blind/prereg.json` and `blind/key.json`, `ladder1_*` refers to the pilot and `top_anchor_q90` to Top note.
  `ear_1nov` holds the composer's keys chosen by ear on the canvas before the study.

## Stored data

| Path | Content |
|---|---|
| `*/key.json` | Clip code to voice and key (shift). In `pilot/`, `pred` is the Median rule's key; in `blind/`, `pos` is the position in the order played |
| `*/answers/composer_*.json` | The composer's answers as saved by the rating page: per ladder (`steps` with tag and strain, `sweet`), or per clip (`register`, `strain`, `broken`) |
| `blind/prereg.json` | The frozen rule, hypotheses, primary measure and each voice's predicted keys |
| `blind/order.json` | The order the blind clips were played in |
| `data/profiles.json` | Per voice: percentiles of the sung pitch and the reference clip's median; per song: note count and percentiles; per case: each rule's key. Written by `make_profiles.py` |
| `data/render-pitch.json` | Per rated render: median sung pitch minus the intended key, in semitones. Written by `render_pitch.py` |
| `llm/results/<model>.json` | Every text-model answer (8 cases, 4 conditions, 3 draws; the answer cut to 600 characters) with the parsed shift |
| `llm/listen-results/<model>.json` | Every audio-model answer: where the singer sits (`perceive`) and the key (`key`) |
| `llm/listen-truth.json` | Measured low, centre and high note of each 30-second clip the audio models heard, and the clip's start |
| `llm/prompts.jsonl` | The exact prompt text of every case and condition |

## What is not distributed

- Audio. The clips the composer rated, the renders they were cut from, the singers' recordings and reference clips,
  and the 30-second clips the audio models heard. The singers did not consent to publication of their voices. Clips
  are referred to by code.
- The rating pages. They played the clips from the claude.ai artifact runtime and do nothing without them.
- The singers' pitch tracks (`pre/vocal_f0.npy`, from commercial recordings) and the songs' fitted scores (note-level
  melodies with lyrics). `data/profiles.json` keeps only the percentiles and rule keys derived from them.
- The pitch tracks of the rated renders. They follow the melody; `data/render-pitch.json` keeps one offset per clip.
- The pictures shown in the `image` condition. They plot the song's notes and are rebuilt by `llm/run_center.py`.

## Rerun

The derived data, from the song projects (`ARRANGE_RUNS`, one folder per song as written by the skills; the voices
are in `$ARRANGE_RUNS/color-purple/voices/<voice>/`):

```
ARRANGE_RUNS=/path/to/runs python3 make_profiles.py
```

The clips, from the key sweep renders (`$ARRANGE_RUNS/all-the-things-cohen/build/sweep/voice/<voice><shift>`, sung by
SoulX-Singer with 64 steps). Each script writes to `build/<round>/` and reads the stored keys of earlier rounds, so
the codes come out the same. ffmpeg with libmp3lame is needed.

```
python3 pilot/make_clips.py
python3 blind/make_clips.py
python3 recheck/make_clips.py
python3 side-by-side/make_clips.py
python3 groban-recheck/make_clips.py
ARRANGE_SOULX=/path/to/SoulX-Singer python3 measure_clips.py build/pilot/clips build/f0/pilot
ARRANGE_SOULX=/path/to/SoulX-Singer python3 measure_clips.py build/blind/clips build/f0/blind
python3 render_pitch.py --f0 build/f0/pilot build/f0/blind
```

The language models, writing to a new folder so the stored results are not merged with yours. The text conditions
run from `llm/prompts.jsonl`; the `image` condition needs `ARRANGE_RUNS`.

```
python3 llm/run_center.py --model claude-sonnet-5-5 --draws 3 --out results-new --conds name numbers anon
ARRANGE_RUNS=/path/to/runs python3 llm/run_center.py --model claude-sonnet-5-5 --draws 3 --out results-new
vllm serve Qwen/Qwen3.5-27B-FP8 --served-model-name qwen3.5-27b-fp8 --max-model-len 40960 --gpu-memory-utilization 0.90 --max-num-seqs 16 --reasoning-parser qwen3 --port 8011
ARRANGE_RUNS=/path/to/runs python3 llm/run_center.py --model qwen3.5-27b-fp8 --base-url http://localhost:8011/v1 --draws 3 --out results-new
vllm serve google/gemma-4-E4B-it --served-model-name gemma-4-e4b-it --max-model-len 16384 --gpu-memory-utilization 0.85 --max-num-seqs 8 --port 8011
ARRANGE_RUNS=/path/to/runs python3 llm/run_listen.py --model gemma-4-e4b-it --base-url http://localhost:8011/v1 --draws 3
```

Claude models are called through the Claude Code CLI (`claude -p`) with the system prompt "You are an experienced
vocal arranger.", from an empty temporary folder, with tools disabled except `Read` for the picture. The paper's runs
called the CLI from a scratch folder outside any project. Gemma 4 31B was served as
`RedHatAI/gemma-4-31B-it-FP8-block` with the Qwen flags minus the reasoning parser. The open text models used each
server's default sampling and up to 24,000 tokens; the audio models used temperature 0.7. The Qwen2.5-Omni 7B run
(`Qwen/Qwen2.5-Omni-7B`, same flags as Gemma 4 E4B) was started by hand. One Qwen 3.5 27B image answer and one
Omni pitch answer did not parse; they are counted as unparsed and left out of the means.

| Variable | Used for | Default |
|---|---|---|
| `ARRANGE_RUNS` | song projects: fits, voices, sweep renders | `runs/` at the repository root |
| `ARRANGE_SOULX` | SoulX-Singer checkout with its preprocessing models, for `measure_clips.py` | none |
