# Curated edits on the score canvas

Paper: Section 5.1, "Curated edits on the canvas".

62 edit requests on the sung lines (fits) of three songs, written in the style of the composer's own messages. They vary
what changes (a pitch, words, a note added or removed, the sounds sung, timing, which syllable sits on which note), how
the place is named (bar and beat as the canvas numbers them, the grey syllable number, the word, a pitch name, or a
screenshot of the canvas with the note circled) and how exactly a time is given. Kinds: single changes, lists, patterns
("every the should sound like thee"), passages, symptoms ("the light after sky comes in late"), revisions of an earlier
edit, and questions about the fit. Nine requests are incomplete on purpose; the right answer to those is a question.

## Arms

| Arm | What the model gets | What it answers |
|---|---|---|
| `typed` | The lyric skill's notes, the fit as a table numbered the way the canvas numbers it, the sounds each syllable is sung with, and the edit vocabulary, in one prompt | A JSON list of edits (`set`, `move`, `shift`, `insert`, `delete`, `pronounce`, `ask`, `say`) |
| `bare` | The fit as raw JSON rows and the request | The whole edited fit, or a question |
| `skill` | Claude Code with the same notes installed as a Claude skill (`skill_arm/arrange-lyrics/`), which it loads itself; two scripts show the fit and apply edits | Whatever it does to `song/fit.json`, and its reply |

Scoring is by outcome. The edited fit must equal the gold fit (start within 0.05 s and end within 0.10 s on the rows the
edit touches, 0.02 s elsewhere; pitch, kind and text exact), or pass the item's check (vague timing), or give the gold
sounds (pronunciation). An incomplete request passes on a question with no edit. A question about the fit passes when
the answer names what it should.

## Reproduce the paper's numbers from the stored results

No model is called.

| Paper | Command | Where |
|---|---|---|
| Typed against raw rows per model, items better/worse, sign test | `python3 suite.py --items` | `ITEMS.md`, last table |
| Requests every model passed (the 11 unit tests) | `python3 suite.py --items` | `ITEMS.md`, tier `basic` |
| Incomplete requests, screenshots, symptoms, by kind | `python3 suite.py --table` | `TABLE.md` (sum the three Claude rows) |
| Installed skill against the prompt, questions on complete and incomplete requests | `python3 skill_arm.py --table` | `results-skill/TABLE.md` |

`results/<model>.json` holds every try of the `typed` and `bare` arms (62 items, 3 draws each); `results-skill/` holds
the `skill` arm for the three Claude models.

## What is not distributed

The fits are note-level transcriptions of copyrighted melodies (*Theme from The Color Purple*, *Someday My Prince Will
Come*, *All the Things You Are*), so the built items (`build/items.json`), the canvas screenshots and the song projects
are not in this repository. For the same reason, the `bare` arm's answers that reproduce the whole fit are withheld
(`"answer": null`, with `answer_withheld` saying why); their scores are kept. The item definitions in `items.py`
(requests, gold edits, checks) are complete.

One `typed` try (Gemma 4 31B, `cp22`, third draw) was first scored invalid because the sounds step of the scorer
timed out. It was rescored from the stored answer and is marked with a `note`.

## Rerun

Rerunning needs the song projects. Point `ARRANGE_RUNS` at a folder with one project per song (as written by the
`arrange-listen` and `arrange-lyrics` skills), then:

```
python3 suite.py --build        # canvas positions, gold fits, screenshots -> build/
python3 suite.py --selftest     # every gold edit scores correct; no change fails; asking passes only where it should
python3 suite.py --model claude-sonnet-5-5 --draws 3
python3 suite.py --model qwen3.5-27b-fp8 --base-url http://localhost:8000/v1    # any OpenAI-compatible server
python3 skill_arm.py --model claude-sonnet-5-5 --draws 3
```

Claude models are called through the Claude Code CLI (`claude -p`). Calls with a screenshot and the `skill` arm run in a
fresh temporary folder, so the CLI loads no project instructions or memory. Environment variables:

| Variable | Used for | Default |
|---|---|---|
| `ARRANGE_RUNS` | song projects | `runs/` at the repository root |
| `ARRANGE_ANALYSIS_PY` | Python with the analysis dependencies, for `--build` | the current Python |
| `ARRANGE_G2P_PY` | Python with `g2p_en`, for the sounds step | the current Python |
| `ARRANGE_PLAYWRIGHT_PY` | Python with Playwright and Chrome, for screenshots | the current Python |
