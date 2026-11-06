# The ARRANGE pipeline responsibility matrix — one owner per decision

Identical copy in `/arrange-listen`, `/arrange-brainstorm`, `/arrange-plan` and
`/arrange-render`. If two skills seem to disagree about who owns something,
THIS file wins; fix the other one.

The chain: Listen (`/arrange-listen`) → Play the Line, Fit, Sing
(`/arrange-lyrics`) → Plan (`/arrange-brainstorm`, `/arrange-plan`) → Mix
(`/arrange-render`).

The piano recording exists *before* anything else and is the spine every layer
must fit. So analysis comes first, and the clock is measured from the start:
there is no estimated phase to swap out later.

## The one authoritative editorial handoff

**`arrangement.json`, produced and finalized by `/arrange-plan`, is the single
authoritative statement of the arrangement.** It is what the creator approved
in the tracks page, and it is the only editorial input `/arrange-render` accepts.
Render translates and executes; it decides nothing.

## Ownership

| Thing | Owner (source of truth) | Consumers | Editable by | Validated at |
|---|---|---|---|---|
| The piano recording (the spine) | the creator | everything | nobody — a new recording is a new project | listen (probe) |
| Transcription (piano MIDI, pedal) | listen (`transcribe.py`) — a *fact with a confidence*, never silently corrected | brainstorm (context), plan | creator may hand-fix the MIDI; mark `inspection: creator-checked` | listen build |
| **Tempo map** (bar:beat ↔ seconds) — the clock | listen (`analyze.py`) — **measured** from the performance, or rebuilt from the creator's taps (`/arrange-lyrics` `take.py`); `method` says how | plan (the only skill that converts), render (reads derived seconds only) | creator may tap/confirm downbeats; nobody edits derived seconds | listen build; plan `clock.py` refuses a map with gaps |
| Key | listen | brainstorm, plan, the Score Canvas (accidentals) | creator corrects; `source: creator` | listen build |
| Sections (intro/verse/chorus… with bar ranges) | listen proposes; **brainstorm confirms** — cells are sections | plan | creator | notebook parse (cell ↔ section match) |
| Melody line (skyline MIDI, range) | listen | brainstorm (syllable counts), `/arrange-lyrics` other ways in | creator may hand-fix; `inspection: creator-checked` | listen build |
| The played line and the fit (`lyric-fit.json`: words on notes, sounds per syllable) | lyrics (`take.py`, `merge_take.py`, `edit_fit.py`) | the Score Canvas, `sing.py` | **creator** owns every placement; the agent applies typed edits | `edit_fit.py` refuses mechanical errors |
| Voice reference and consent (`CONSENT.txt`) | lyrics (`make_voice.py`) | `sing.py` | creator | `sing.py` refuses a voice without consent |
| Key for a copied voice | lyrics (`center.py` proposes; four rules printed) | `transpose.py`, `sing.py` | **creator** decides by ear | - |
| Sung preview and the entry check | lyrics (`sing.py`, `mixcheck.py`) | creator | nobody (regenerate) | entries reported per line |
| Dynamics curve (per-bar RMS) | listen | plan (swell/enter hints), render (loudness targets) | nobody (fact) | — |
| Human takes catalogue (`asset-catalog.json`: recorded guitar, scratch vocal…) | written by hand or a separate tool (no catalogue script ships) — identity + probed facts; `unresolved` when unknown, never guessed | plan (binds), render | nobody hand-edits ids | render refuses missing facts |
| Arrangement intent, prose, mock layer components | brainstorm (`ARRANGEMENT.md`) | plan (binds them) | creator ↔ agent in conversation | notebook parse |
| Lyrics (the words, per section) | brainstorm — the creator's text, never rewritten unasked | plan (syllable fitting) | creator | notebook parse |
| Bar coverage ballpark (which bars have no layer) | brainstorm (`coverage.py`) — badged rough | creator | nobody (derived) | — |
| Variants of real choices (strings from bar 1 vs chorus) | brainstorm | plan (creator picks one) | creator | notebook parse |
| **Anchors** (bar:beat identity; seconds derived) | plan | render (reads derived `t0/t1` only) | creator, in the tracks page | build validate (bar↔time consistency) |
| **Route** per layer (audio vs score vs take vs stub) | plan (`bind.py`, see `routing.md`) | render | creator (authoritative once `chosen_by: creator`) | build validate |
| **Conditioning order** — what each generated layer *hears* | plan (`hears` + `order`) | render executes in that order | creator | build validate (no cycles, hears only earlier layers or piano) |
| Generation prompts, instrument class, params, variant count | plan | render | creator | build validate (class ∈ backend vocabulary) |
| Sung layer in the plan (entry, exit, what it hears) | plan | render | creator | build validate (a sung layer needs a score condition) |
| The Tracks HTML — the human control surface | plan (`tracks.py`) | creator | — | — |
| Revisions (typed operations, deterministic apply) | plan (`revise.py`; the agent turns words into operations) | — | creator authors them | refused or unresolved operations are reported |
| Finalized `arrangement.json` | **plan** | render, tracks | creator via revisions only | build validate |
| Stems (zero-aligned, full-length, same SR) | render | DAW | nobody (regenerate) | render parity |
| Verification badges per stem (key/beat/loudness/pitch/leak) | render (`verify.py`) | creator, plan (on reject → revise) | nobody (measured) | render report |
| Best-of-N selection | render proposes by metrics; **creator decides** by ear; `chosen_by` recorded | — | creator | report |
| Mix preview | render (`mix.py`; the sung preview in lyrics) — a *preview*, never the deliverable | creator | — | — |
| Finished mix of the voice over the piano (vocal chain, −14 LUFS) | render (`polish.py`) | creator | creator by ear | — |
| Logic Pro export (stems + tempo/marker SMF + IMPORT.md) | render (`export.py`, `smf.py`) | Logic | nobody (regenerate) | parity: every layer → one stem or stub |
| Parity (no layer silently dropped) | render | — | — | refuses on any drop |

## What each module must NOT do

- **listen**: no arrangement decisions — it never proposes what to add; it
  reports what is there. Its section labels are a *proposal* brainstorm may
  rename or merge.
- **brainstorm**: no seconds, no model names, no prompts tuned to a backend,
  no file paths. Bars are the only numbers. Model-agnostic on purpose: models
  churn yearly, notebooks should not.
- **plan**: never re-estimates the clock outside `clock.py`; never overrides a
  `chosen_by: creator` layer (a real conflict is explained once, then the
  creator decides); never renders audio.
- **render**: no editorial decisions at all — not which instrument, not where
  it enters, not what it hears, not which variant ships (it ranks; the creator
  chooses). It executes, measures, exports.
