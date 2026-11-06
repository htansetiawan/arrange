---
name: arrange-plan
description: Turn an ARRANGEMENT.md notebook plus piano-analysis.json (and any human-take catalogue) into arrangement.json, the plan of which layers exist, where each enters and exits as bar:beat anchors with seconds derived from the measured tempo map, how each is produced (ACE-Step for instrument layers, SoulX-Singer for sung layers, a human take, or a silent stub) and what each generated layer hears, plus ARRANGE-TRACKS.html, a page with one lane per layer. Revisions are typed operations applied by a script, so a change touches only what was asked. Use whenever someone wants to plan or bind an arrangement, turn a notebook into generation jobs, decide which model makes which part or what it hears, see what is unbound or undecided, stub a part that does not exist yet, revise a placement, or hand a finished plan to /arrange-render. The only place bars are converted to seconds.
---

# /arrange-plan

The Plan step of the ARRANGE chain:

Listen → Play the Line, Fit, Sing (`/arrange-lyrics`) → **Plan** (`/arrange-brainstorm`, `/arrange-plan`) → Mix (`/arrange-render`)

You take the creator's **notebook** (mock layers, bars only), the
**analysis** (measured facts, the tempo map), and the **catalogue** of human
takes, and you produce **`arrangement.json`** plus **`ARRANGE-TRACKS.html`**, the
page they actually look at. Read `references/arrangement-schema.md` first; you
own producing it.

Two jobs, equally important:

- **Interpretation.** The notebook is deliberately loose. "Strings come in
  halfway through the verse" is normal input. Interpret it against the
  analysis (halfway through bars 9–24 is bar 17), then *show what you
  interpreted* and let them correct it. **Never fail on a loose notebook.**
- **Binding.** Every component either binds to a **generation job**, to a
  **human take** from the catalogue, or becomes a **stub** — a silent stem of
  exact length — so the Logic session imports complete, with visible empty
  tracks instead of missing parts.

Precision here is **production-close, not final**. Levels, final entry nudges
and the choice between variants happen by ear, in Logic.

## Refuse to run without a notebook

| Missing | What you do |
|---|---|
| The notebook | **Stop.** Say what is missing and offer `/arrange-brainstorm`. Do not improvise an arrangement from the analysis — the notebook is the creator's document. |
| The analysis | **Stop.** You cannot convert bars to seconds without the tempo map. Offer `/arrange-listen`. |
| The catalogue | Fine. Every `take`-flavoured component becomes a stub with a reason; say that binding to real takes needs `/arrange-listen`'s catalogue. |
| Lyrics for a `<vocal>` | Fine to proceed as a stub for the vocal; a sung layer with no words cannot be scored. Ask once. |

## The contract (see references/responsibility-matrix.md)

**This skill produces the authoritative finalized `arrangement.json` — the
single editorial handoff to `/arrange-render`.** Everything editorial is decided
here and only here: which layers exist, anchors, route per layer, the prompt
or score each job gets, what each layer hears, and the render order. Render
executes; it decides nothing.

Three rules with teeth:

- **A `chosen_by: creator` layer is authoritative.** Never silently rebind or
  re-route it. On rebuild, run `build.py … --preserve old-arrangement.json`
  so every creator choice survives; a genuine conflict is flagged once as a
  question and the creator decides.
- **Surface unresolved facts BEFORE handoff, in musical language.**
  `open.unresolved_specs` lists what is still unknown ("the downbeat in bars
  17–20 is ambiguous, so the strings' entry there is a guess"). Never "layer
  L2 anchor confidence 0.4".
- **Anchors are bar:beat.** `t0`/`t1` are a derived cache. If the creator
  re-records or re-taps the tempo map, times change and anchors do not, so
  re-timing never re-plans. `validate.py` refuses an arrangement where a
  layer's seconds disagree with its anchors under the current map.

## The clock — measured, and owned here

There is exactly **one** conversion from bars to seconds, `scripts/clock.py`,
and it reads `piano-analysis.json#tempo_map`. Nothing downstream may convert
anything. There is no estimated clock to swap later: the recording is the
clock. If the map says `rubato: high` and has `unresolved`
bars, every anchor inside those bars gets an `uncertain: true` flag that the
tracks page shows, and the question goes to the creator before handoff.

## Routing — which way does each layer get made?

Read `references/routing.md`. The short version:

| Layer class | Default route | Why |
|---|---|---|
| vocals, backing vocals | **score** → `soulx-singer` | The vocal needs the words on the right notes; the composer's fit from `/arrange-lyrics` (syllables on notes, sounds per syllable) is the score. |
| strings, pad/synth, guitar, bass, brass, woodwinds, fx, keys | **audio** → `ace-step/lego` (one layer at a time) | Audio-conditioned generation follows the recording's rubato and harmony directly, with no transcription errors in the loop. |
| any class the creator recorded | **take** | Theirs wins. |
| anything undecided or unsupported | **stub** | The session still imports complete. |

The route is a plan-level decision the creator can flip. Routes are per
layer, so one arrangement can mix them. A score-route orchestral layer is not
implemented in this release and stays a stub with a reason.

**Conditioning order is editorial.** Vocal first (hears piano only), then
pads/strings (hear piano + vocal so they leave room for the voice), then
anything rhythmic. Write it into `order` and each layer's `hears`; render
follows it exactly. If the creator says "the strings should ignore the
vocal", that is a one-field change, not a re-plan.

## Workflow

```
python3 scripts/notebook.py   parse  ARRANGEMENT.md -o notebook.json
python3 scripts/clock.py      check  piano-analysis.json                      # refuses gaps; lists uncertain bars
python3 scripts/bind.py       bind   notebook.json piano-analysis.json [asset-catalog.json] -o bindings.json [--variant chorus=A]
python3 scripts/build.py      build  notebook.json bindings.json piano-analysis.json \
                                     -o arrangement.json [--preserve old-arrangement.json]
python3 scripts/validate.py   arrangement.json piano-analysis.json
python3 scripts/tracks.py     arrangement.json piano-analysis.json ARRANGE-TRACKS.html [--audio piano.mp3]
```

1. **Parse** the notebook; carry every `raw` through so nothing is lost.
2. **Check the clock** and collect uncertain bars.
3. **Bind** each component: route, backend, class, prompt (component text +
   class + key/tempo/vibe from analysis + "no added vocals" for non-vocal
   audio jobs), anchors from `@`/`~` markers or prose, `hears` from the
   default order. Where the notebook has variants of a cell, `--variant`
   picks one. A sung layer's words are fitted to notes in `/arrange-lyrics`,
   not here.
4. **Build** `arrangement.json`; derive `t0`/`t1`; preserve creator choices.
5. **Validate**: anchors ↔ seconds, `hears` acyclic and backward, every
   class supported by its backend, every layer has a route.
6. **Render the tracks page** and deliver it with the JSON. Walk the creator
   through what you interpreted, the prompts as written, and the open
   questions. Then take revisions.

`examples/` holds a synthetic notebook, analysis and the plan built from them
(`arrangement.example.json`, variant A of the chorus).

## Revisions — typed edits only

The creator says *"strings two bars later"*, *"vocal hears nothing but
piano"*, *"swap the pad for guitar in the chorus"*, *"make the brass a stub
for now"*. You turn each request into operations from the fixed vocabulary
(`python3 scripts/revise.py ops` prints it) and the script applies them:

```
python3 scripts/revise.py apply arrangement.json piano-analysis.json --op '{"op":"shift_entry","layer":"strings","by_bars":2}'
python3 scripts/revise.py apply arrangement.json piano-analysis.json --ops ops.json [--reason "..."] [--keep]
```

It prints what it applied, what it refused and why, the open questions, the
layers made stale and every changed path. A refused operation exits 2; a
revision that would leave an invalid plan is not written (exit 1). Anything the
words do not map to becomes an `ask` operation, recorded with nothing
changed: ask the creator. Nothing is silently dropped. After a revision,
re-run tracks.

## Handoff

When the creator says it's right, say plainly what `/arrange-render` will do:
how many jobs, in what order, which backends, which layers are stubs, and
which open questions remain (render will trust the plan as-is for those).
Then hand off.
