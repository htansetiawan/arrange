# The ARRANGE Arrangement Notebook format (`ARRANGEMENT.md`)

The notebook is the artifact `/arrange-brainstorm` produces and the creator edits.
It is **Markdown**, meant to be read and rearranged by a musician in any text
editor, with no tooling. Two rules follow from the medium:

1. **Bars are the only numbers.** No seconds, ever — seconds belong to the
   tempo map in `piano-analysis.json`, which `/arrange-plan` reads. A notebook that
   says "strings enter at bar 17" survives a re-recording with different
   rubato; one that says "at 1:12" does not.
2. **Components are layers, not a sequence.** In an arrangement almost
   everything in a section sounds at once, so every component in a cell is a
   layer that is **active for the whole cell unless it says otherwise**.

Everything below is **tolerant**. The parser never rejects a notebook.
Anything it cannot classify becomes an `unknown` component carrying the raw
text, and `/arrange-plan` asks the creator about it rather than guessing.

---

## 1. Shape

```markdown
---
piece: Evening hymn (solo piano cover)
analysis: piano-analysis.json      # produced by /arrange-listen
vibe: intimate, cinematic, never busy
singer: alto, breathy, close-mic    # optional, applies to every <vocal>
---

## intro (bars 1–8)

Keep the piano alone. Maybe a hint of room.

<pad: barely-there warm synth pad, one chord per bar, under the piano ?>

## verse 1 (bars 9–24)

<vocal: intimate, conversational, stays below the piano's top line>
<lyrics:
Red brick and elm, the morning bell
A hundred doors, a single hall>
<strings: soft sustained pad, violas and cellos, no vibrato @bar 17>

## chorus (bars 25–40)

<vocal: open and full, harmony on the last line !>
<lyrics:
...>
<strings: full section, long swell into bar 25, release at 40>
<guitar: fingerpicked nylon, doubles the left hand rhythm ~bars 33–40>
```

- **Front matter** (optional) carries piece-level facts. `analysis` points at
  the `/arrange-listen` output the cells must line up with.
- **`## heading`** starts a **cell**. A cell is one *section* of the piece and
  should match a section in `piano-analysis.json` by name; the bar range in
  parentheses is optional but recommended (if absent, the analysis's range for
  that name is used; if both are present and disagree, plan asks).
- **`<...>`** is a **component** — a layer in this section. This is the only
  required syntax. Multi-line components are fine.
- **Plain prose outside `<...>`** is a **note to the skill**: direction, not
  content. It is carried to `/arrange-plan` as the cell's `note`.

## 2. Component types

Type is inferred from the word before the colon. Inference is a convenience;
the creator never has to declare a type, and plan asks when unsure.

| Type | Triggered by | Maps to generator class |
|---|---|---|
| `vocal` | vocal / voice / sing / lead | `vocals` |
| `backing` | backing / harmony / choir / oohs | `backing vocals` |
| `lyrics` | lyrics / words | — (text for the vocal layer in this cell) |
| `strings` | strings / violin / viola / cello / string pad | `strings` |
| `pad` / `synth` | pad / synth / texture / drone | `synth` |
| `guitar` | guitar / nylon / acoustic / electric | `guitar` |
| `bass` | bass / upright / sub | `bass` |
| `keys` | keys / rhodes / organ / celesta / second piano | `keyboard` |
| `drums` | drums / kit / brushes | `drums` |
| `percussion` | percussion / shaker / taiko / hand drums | `percussion` |
| `brass` | brass / horns / trumpet / trombone | `brass` |
| `woodwinds` | woodwinds / flute / clarinet / oboe | `woodwinds` |
| `fx` | fx / riser / reverse / ambience / room | `fx` |
| `unknown` | nothing matched | — (plan asks) |

The class column is the *shared vocabulary* every backend must map onto (it is
the 12-class set ACE-Step 1.5 uses for Lego/Complete/Extract, which is the
most common denominator today). A backend that cannot produce a class says so
at plan time, not at render time.

## 3. Extent and entry — bars, nothing else

By default a component sounds for the whole cell. Modifiers narrow that:

| Marker | Meaning | Example |
|---|---|---|
| `@bar N` | enters at bar N (to end of cell) | `<strings: … @bar 17>` |
| `~bars A–B` | sounds only in bars A–B | `<guitar: … ~bars 33–40>` |
| `@bar N:B` | beat-precise entry | `@bar 17:3` |
| plain English | "comes in halfway", "only on the last line" | plan interprets and *shows* its interpretation |

Prose like "swell into bar 25", "release at 40", "drop out for the last two
bars" is direction: plan turns it into anchors and an automation hint and
reports what it did. The `@`/`~` markers are faster; the sentence is never
wrong.

## 4. Decision markers

- `!` — **creator-decided**. Plan binds it faithfully and never re-argues it.
  Once bound it carries `chosen_by: creator`.
- `?` — tentative. Plan may propose an alternative or ask.
- Neither — a proposal of the skill's; plan treats it as `chosen_by: claude`.

## 5. Variants

Where a real choice exists, cells may fork with the heading convention
`## chorus (variant A)` / `## chorus (variant B)`. Variants must differ in
kind (strings from the top vs. entering at the chorus; a vocal verse vs. an
instrumental one), not in wording. Plan asks the creator to pick one before
binding; it never renders both unless asked.

## 6. The `lyrics` component

Lyrics belong to the creator. Lines are kept verbatim, one line per lyric
line. Plan fits syllables to the extracted melody for that cell and reports
mismatches ("verse 1 has 31 syllables, the melody has 28 notes") as questions,
never as silent edits. A cell with `<lyrics>` but no `<vocal>` gets a default
vocal layer from the front-matter `singer` and a flag saying so.

## 7. What the notebook does not contain

No seconds. No model names. No prompts tuned to a backend. No file paths. No
mix levels. Those are plan's and render's, and putting them here would couple
the creator's document to this year's tooling.

## 8. Parsed form

`scripts/notebook.py parse ARRANGEMENT.md -o notebook.json` emits:

```json
{
  "piece": "Evening hymn (solo piano cover)",
  "front": {"analysis": "piano-analysis.json", "vibe": "...", "singer": "..."},
  "cells": [
    {"name": "verse 1", "bars": [9, 24], "variant": null, "note": "...",
     "components": [
       {"type": "vocal", "class": "vocals", "text": "intimate, conversational…",
        "enter": null, "span": null, "decision": "claude", "raw": "<vocal: …>"},
       {"type": "lyrics", "lines": ["Red brick and elm, the morning bell", "…"]},
       {"type": "strings", "class": "strings", "text": "soft sustained pad…",
        "enter": {"bar": 17, "beat": 1}, "span": null, "decision": "claude"}
     ]}
  ]
}
```

`raw` is always preserved so nothing the creator wrote is lost in parsing.
