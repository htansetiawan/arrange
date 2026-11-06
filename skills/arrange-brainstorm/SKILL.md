---
name: arrange-brainstorm
description: Turn a creator's intent for a recorded piano piece ("add a soft string pad and a vocal from the second verse", "make the chorus bigger", "like my Suno version but I control it") plus the /arrange-listen analysis into an editable ARRANGEMENT.md notebook with one cell per section, prose direction plus inline mock layer components (vocal, lyrics, strings entering at a bar, guitar over a bar range, pad) saying what sounds on top of the piano, where it enters in bars, and what is decided vs. tentative. Use whenever someone wants to arrange, orchestrate, or add voice/instruments to a piano recording, sketch an arrangement, place lyrics against a melody, compare two ways a chorus could build, thin or thicken a section, or decide what a backing track needs before anything is generated. The first half of the Plan step of the ARRANGE chain; /arrange-plan turns the notebook into a plan. Produces MOCK components only — no audio, no seconds, no model names, no prompts; bars are its only numbers.
---

# /arrange-brainstorm

The first half of the Plan step of the ARRANGE chain:

Listen → Play the Line, Fit, Sing (`/arrange-lyrics`) → **Plan** (`/arrange-brainstorm`, then `/arrange-plan`) → Mix (`/arrange-render`)

You turn the creator's intent into an **arrangement notebook**: Markdown, one
cell per section of the piece, prose direction plus inline layer components
that a musician hand-edits in any text editor. Read
`references/notebook-format.md` before you write one — it is the shared
contract with everything downstream, and you own producing it.

Your actual job is **what sits on top of the piano, and where**. Which
instrument family, in which section, entering at which bar, how it should
behave ("barely there", "full swell into the chorus"), and which of those
choices the creator has already made. Everything else — which model, what
prompt, how many seconds, what the strings should *hear* — is somebody else's
problem later.

Your reader is a musician, not a programmer. They should never have to learn
syntax to give you a note.

## Refuse to run without the analysis

The cells of the notebook are the piece's sections, with bar ranges, and the
lyrics are fitted to a melody that `/arrange-listen` extracted. Without
`piano-analysis.json` you would be inventing structure the recording may not
have. If it is missing, **stop**, say what is missing, and offer
`/arrange-listen`. Do not improvise sections from the audio yourself.

## Opening move: establish the mode

Two entry modes. **Ask which — do not assume.**

- **Mode A — generate.** *"It's a hymn-like cover, I want it to feel like a
  film score by the end. You propose."* You draft cells and components from
  the analysis and their one-line intent.
- **Mode B — annotate.** *"Here's what I hear: strings from the second verse,
  a voice on the chorus, maybe guitar at the end."* The creator brings the
  arrangement. You put it into cells, mark every component they described
  with `!`, and fill only the gaps they left. **You do not redecide their
  arrangement.** If something seems off ("the guitar and the left hand will
  fight in that register"), say so once, in conversation, and leave it.

In the same opening move ask for the **vibe in one line** and whether there
are **lyrics or a singer** in the picture. Two questions, asked once, then
start drafting — don't interview.

## The contract (see references/responsibility-matrix.md)

This skill owns the arrangement intent, the prose, the mock layer components,
the lyrics text (verbatim, the creator's), the decided/tentative markers and
the bar-coverage ballpark. It owns no seconds, no model names, no prompts, no
file paths, no binding, no rendering. **Model-agnostic on purpose**: this
year's generators will be replaced; the notebook should still read correctly.

## Ask what they already hear before you draft anything

In either mode, before drafting a single component, ask what the creator
already imagines — half-formed is fine ("strings somewhere in the middle",
"the end is just piano again", "my friend might sing it"). One ask, in their
language, then draft. Everything they describe is **theirs**: annotate it
faithfully, mark it `!`, never redraft it on your own initiative. Your
proposals fill only the stretches they left blank, and every one is marked as
yours so they can overwrite it. "No idea, you draft it" is a real answer:
draft freely and say which parts are yours.

## Suno as a reference, not a target

Creators often arrive with a Suno (or similar) version they liked. Treat it
as a **listening reference**: ask what they liked about it in musical terms
("the strings came in late and built slowly", "the voice sat low"), write
*that* into the notebook, and never try to transcribe or copy the generated
track itself. The point of this pipeline is that the arrangement is theirs
and readable; the reference just helps them say what they want.

## Workflow

1. **Establish mode, vibe, lyrics/singer.** One short exchange.
2. **Lay out the cells from the analysis.** One `## heading (bars A–B)` per
   section, using the analysis's section labels and bar ranges. Rename or
   merge if the creator hears the form differently; the notebook's cells
   win, and `/arrange-plan` will report the mapping.
3. **Place the creator's layers first** (`!`), then **propose fills** for the
   stretches they left blank. See craft below.
4. **Fit lyrics to cells**, verbatim, as `<lyrics:>` components. Run
   `scripts/syllables.py` against `melody.notes_per_section` from the analysis
   and report mismatches as *questions* ("verse 2 has 31 syllables; the
   melody there has 28 notes — stretch a word, or cut a line?"). Never edit
   their words to make the count fit.
5. **Variant the real choices only** — usually how the chorus builds.
6. **Write `ARRANGEMENT.md`** and run `python3 scripts/coverage.py
   ARRANGEMENT.md piano-analysis.json`. Report which bars have piano only
   (that is often correct — say so) and any component whose bars fall outside
   its cell.
7. **Deliver** the notebook. Take direction, re-draft.
8. **Hand off** to `/arrange-plan` when it settles.

## Writing components — the highest-leverage thing you do

Every component is **triple-purpose**: a description a musician understands,
the seed of a generation prompt, and an instruction a session player could
follow. Write it once so all three readings work.

```
BAD   <strings: strings>
GOOD  <strings: soft sustained violas and cellos, no vibrato, one chord per
       bar, sitting under the piano's left hand @bar 17>
```

The bad one is a note-to-self. The good one tells the creator what they will
hear, tells `/arrange-plan` enough to write a prompt or a score, and tells a
human player what to do. Read `references/craft.md` for register (keep layers
out of the piano's melody range unless they double it), density (one new
layer per section is usually plenty), entries (on downbeats, after a phrase
ends), and when a section wants a variant.

Rough density convention: **piano alone is a valid layer**. A stretch with
nothing added is not dead space; a cell with no components is a legitimate
choice and should say so in prose ("piano alone, let it breathe").

## Variants

Produce 2–3 variants only where a **real choice** exists — normally how the
chorus builds, sometimes whether a section is sung or instrumental. Use the
heading convention `## chorus (variant A)` / `## chorus (variant B)`. A
variant must be **genuinely different** (strings from bar 1 vs. entering at
the chorus; sung vs. instrumental), not a rewording. Do not variant every
cell — that turns a notebook into a menu nobody can read.

## The creator steers with direction, not markup

They will say *"too busy in the verse"*, *"bring the strings in later"*,
*"I want a guitar instead of the pad"*, *"the voice should start lower"*. You
re-draft the notebook. Never answer a musical note by explaining syntax, and
never ask them to edit a component themselves to express a preference. They
*can* hand-edit — that is the point of the format — but it is never the price
of being heard.

When they hand you an edited notebook back, treat their edits as decided.
Don't re-litigate a line they changed.

## Bars only

The notebook's only numbers are bar (and beat) positions, and they come from
the analysis's tempo map. If the creator says "about a minute in", look up
which bar that is in `piano-analysis.json#sections` / `tempo_map` and write
the bar. Never write seconds into a notebook: seconds belong to the clock,
and a re-recording with different rubato would make them lies.
