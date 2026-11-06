# Routing — how each layer gets made, and why it's a plan decision

A route is the production path for one layer. It is chosen here, shown in
the tracks page, and executed verbatim by render. Four routes exist.

## `audio` — audio-conditioned generation (default for instrument layers)

Backend: **ACE-Step 1.5** base checkpoints (`acestep-v15-base` 2B or
`acestep-v15-xl-base` 4B; the sft/turbo variants cannot do this).

- `ace-step/lego` ("Add Layer"): one stem of one class, in the context of
  existing audio, optionally only inside a repaint window. Use for one layer
  at a time — the normal case.
- `ace-step/complete` ("Complete Track"): several classes at once around a
  bare source; the result is a mix, not a stem. The plan can name it, but the
  shipped backend (`backends/ace_step.py`) runs Lego only.

Classes available: vocals, backing vocals, drums, bass, guitar, keyboard,
percussion, strings, synth, fx, brass, woodwinds. A notebook type outside
this set is mapped (pad → synth) or asked about.

Why default here: the generator listens to the actual recording, so rubato,
voicings and dynamics are followed without a transcription in the loop.

What it costs: the result is audio, not notes. A wrong chord in bar 31 is a
re-render, not an edit. Keep variants ≥ 3; the creator picks by ear.

Prompt construction (plan writes it, tracks page shows it):
`<component text>, <class words>, key <tonic mode>, ~<bpm_mean> BPM, <vibe>,
no added vocals` — the last phrase on every non-vocal job by default.

## `score` — symbolic first, then rendered (default for vocals)

- Vocals → **SoulX-Singer** in score mode. The score is the composer's fit
  from `/arrange-lyrics` (one row per note: the syllable, its sounds, pitch and
  times on the recording's clock); `sing.py` renders it and `register.py` in
  `/arrange-render` records the takes on the plan's sung layer. The plan
  itself does not read the fit; it schedules the layer and what it hears.
- Orchestral layers on request (a re-orchestration of the transcribed piano
  MIDI, then a sampler) are not implemented in this release; such a layer
  stays a stub with a reason.

Why here: the words must land on the right notes, and the composer edits
notes and syllables on the Score Canvas.

## `take` — a human recording from the catalogue

Theirs wins. Plan binds by `asset_id`; `export.py` resamples it and ships it
as a stem, untouched otherwise. A take recorded free of the piano needs its
offset stated in the catalogue (or asked) before export.

## `stub` — silence of exact length

For anything undecided, unsupported, or blocked. Carries a `reason`. Exists
so the Logic session imports complete and the gap is visible as an empty
track rather than a missing part.

## Conditioning order (`order` + `hears`)

Default: vocals first (hear the piano only), then sustained layers (hear
piano + vocal), then rhythmic layers (hear everything so far). The reason to
put the voice early is register: a pad generated against piano + voice tends
to sit around the voice rather than on it. The creator can reorder with one
revision ("strings hear piano only"). `hears` may only reference `piano` or
layers earlier in `order`; validate enforces it.
