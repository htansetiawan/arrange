---
name: arrange-render
description: Render, mix and export an approved ARRANGE plan. Runs the plan's instrument layers with ACE-Step 1.5 (Lego, one layer at a time on the context the plan declares), records every candidate on the plan, measures each one against the piano (chroma, level, vocal pitch), makes a listening preview, polishes the sung voice over the piano into a finished mix (vocal chain, voice in front, -14 LUFS), and exports zero-aligned full-length stems plus a tempo-map and marker MIDI file and import notes for Logic Pro. Use when someone wants to render or re-render a planned layer, hear the plan with its candidates, finish the mix of a sung line over the piano, or get stems into a DAW. The Mix step of the ARRANGE chain. Never decides what goes where (that is /arrange-plan) and never picks a candidate for the creator.
---

# /arrange-render

The last step of the ARRANGE chain:

Listen → Play the Line, Fit, Sing (`/arrange-lyrics`) → Plan (`/arrange-plan`) → **Mix** (`/arrange-render`)

You take the approved **`arrangement.json`** and the piano recording and produce
candidates for each layer, measurements, a listening preview, a finished mix of
the sung voice, and a **Logic Pro import folder**. You make no editorial
decisions: the plan says which layers, where, how, hearing what, in which order.
You execute that, measure the result, and tell the truth about it. Read
`references/arrangement-schema.md` (the input), `references/backends.md` (how
each job runs), `references/verification.md` (what is measured) and
`references/targets.md` (the Logic export) before the first run.

Setup: the backends find ACE-Step and SoulX-Singer through the ARRANGE config or
`ARRANGE_*` environment variables (`docs/setup.md` in the repository). The
scripts import the plan library from `/arrange-plan`, so install the ARRANGE
skills side by side.

## Refuse to run without an approved plan

| Missing | What you do |
|---|---|
| `arrangement.json` | **Stop.** Offer `/arrange-plan`. Do not invent layers from a notebook or a description. |
| The piano recording | **Stop.** Everything is conditioned on it and aligned to it. |
| A backend a job needs (ACE-Step not installed, no base checkpoint) | Render everything else; leave the affected layers stubs with a reason (a `set_stub` revision in `/arrange-plan`). Never substitute a different backend or route on your own: that is a plan change. |
| `open.unresolved_specs` is non-empty | Proceed, trusting the plan as written, and say which layers were rendered under uncertainty. |

## Workflow

Render each layer in the plan's `order`, register its candidates, then measure,
preview and export:

```
# an instrument layer (audio route): ACE-Step Lego on the context the plan declares
python scripts/backends/ace_step.py --plan arrangement.json --layer L4 --spine piano.wav --build build/ [--variants 3] [--seed N]
python scripts/register.py arrangement.json L4 build/L4/candidates.json
# a sung layer: rendered by /arrange-lyrics (sing.py, from the approved fit), then registered here
python scripts/register.py arrangement.json L1 <project>/build/voice/candidates.json
# measure, preview, export
python scripts/verify.py arrangement.json piano-analysis.json --spine piano.wav -o build/measurements.json
python scripts/mix.py arrangement.json --spine piano.wav -o build/preview.mp3 [--window 68 118] [--pick L4=L4c2] [--gain L1=-3]
python scripts/export.py arrangement.json piano-analysis.json --spine piano.wav -o export/logic [--midi analysis/piano.mid]
```

`register.py` marks the first rendered candidate as provisional unless the
creator has already chosen. The creator's choice is a revision in
`/arrange-plan` (`choose_candidate`), never made here.

**Conditioning order matters and is not yours to change.** A layer's context
contains only what the plan says it hears. Rendering the strings before the
vocal because the vocal backend is slow would change what the strings respond
to; if the order is impractical, say so and let the creator decide in the plan.

**Every candidate is full-length and zero-aligned.** It starts at the
recording's t = 0 and is padded with digital silence outside the layer's
window, so in the DAW every stem goes to bar 1 and nothing needs positioning.

## The finished mix of a sung line

For a sung line over the piano, `polish.py` makes the record-like mix: the voice
cleaned and compressed, a small plate, the piano given a little of the same
space and a dip where the consonants live, the voice +6 dB over the piano on
the sung stretch, the bus at -14 LUFS and -1 dBTP:

```
python scripts/polish.py --voice <project>/build/voice/<take>.mp3 --recording piano.wav \
    --score <project>/build/sung-score.json --window 0 70 -o polished.mp3 [--preset light|clean|touch|warm|bright|dry]
```

`--preset dry` gives the same balance with no effects, as an A/B reference.

## Measurements

`verify.py` writes, per rendered candidate: chroma similarity to the piano over
the layer's window, level against the piano, and for sung layers the share of
frames in tune with the score. No thresholds are applied (see
`references/verification.md`). Present the numbers next to the previews, then
**stop and hand the choice to the creator**. If every candidate of a layer is
poor in the same way, that is not a bad seed; it is a plan problem (wrong
prompt, wrong route, wrong context): say which, and point to `/arrange-plan`.

## Export to Logic Pro (see references/targets.md)

`export.py` writes `export/logic/`: `stems/NN_<name>.wav` (zero-aligned,
full-length, 24-bit, numbered in `order` with the piano as `00`; stubs end in
`_STUB`), `tempo-markers.mid` (the tempo map so Logic's grid follows the
performance, the time signature, section markers, the transcribed piano and
the vocal score), `IMPORT.md` (the import steps), and copies of the plan and
the analysis. Every layer appears as exactly one stem; `export.py` refuses to
write the folder if any layer has none, and says which.

## What "done" looks like

1. The export folder, the preview, and the measurements.
2. A one-screen summary in musical language: which layers rendered, which are
   stubs and why, the measurements per candidate, the candidates waiting on the
   creator's ear, and anything rendered under uncertainty.
3. What to change in `/arrange-plan` if they want a different result, never a
   tweak you made yourself.

## The contract (see references/responsibility-matrix.md)

Render owns execution, measurement, parity and export. It does not own which
candidate ships (the creator chooses by ear), nor any change to a layer's
class, prompt, anchors, route or context. When a result is bad, the fix is a
revision in `/arrange-plan`, and you say so.
