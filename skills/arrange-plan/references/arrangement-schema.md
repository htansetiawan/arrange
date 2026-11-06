# `arrangement.json` — the authoritative handoff from `/arrange-plan` to `/arrange-render`

Every editorial decision lives here and only here: which layers exist, where
each enters and leaves (as bar:beat anchors), how each is produced (route and
job), what it hears while being produced, and in what order. Render reads it
and executes; it adds nothing.

```json
{
  "schema": "arrange/arrangement@1",
  "piece": "Evening hymn (solo piano cover)",
  "inputs": {
    "analysis": "piano-analysis.json",
    "notebook": "ARRANGEMENT.md",
    "catalog": "asset-catalog.json"          // optional; human takes
  },
  "clock": {
    "from": "piano-analysis.json#tempo_map",
    "status": "measured",                     // always measured here; see matrix
    "time_signature": "4/4", "bpm_mean": 50.3, "rubato": "high"
  },
  "sections": [ {"id": "s2", "label": "verse 1", "bar_start": 9, "bar_end": 24, "t0": 38.9, "t1": 110.2} ],

  "spine": {"id": "piano", "kind": "take", "path": "takes/piano_master.wav", "class": "keyboard"},

  "layers": [
    {
      "id": "L1", "name": "vocal", "class": "vocals",
      "kind": "generated",                    // generated | take | stub
      "from": {"cell": "verse 1", "component": 0, "raw": "<vocal: intimate, conversational…>"},
      "anchors": {"enter": {"bar": 9, "beat": 1}, "exit": {"bar": 40, "beat": 4}},
      "t0": 38.9, "t1": 182.6,                // DERIVED from anchors via the clock; never hand-edited
      "route": "score",                       // audio | score | take | stub  (see routing.md)
      "job": {
        "backend": "soulx-singer",
        "inputs": {"score": "jobs/L1/vocal.abc", "lyrics": "jobs/L1/lyrics.txt", "ref_voice": "refs/alto_ref.wav"},
        "params": {"transpose": -2, "variants": 3},
        "fit": {"syllables": 59, "melody_notes": 59, "status": "ok"}
      },
      "hears": ["piano"],                     // conditioning context: ids of spine/layers rendered BEFORE this one
      "automation": [],
      "chosen_by": "claude",                  // claude | creator
      "status": "planned",                    // planned | rendered | verified | rejected | shipped
      "notes": "sits below the piano's top line in the verse"
    },
    {
      "id": "L2", "name": "strings", "class": "strings", "kind": "generated",
      "from": {"cell": "verse 1", "component": 2, "raw": "<strings: soft sustained pad… @bar 17>"},
      "anchors": {"enter": {"bar": 17, "beat": 1}, "exit": {"bar": 40, "beat": 4}},
      "t0": 74.1, "t1": 182.6,
      "route": "audio",
      "job": {
        "backend": "ace-step/lego",
        "inputs": {"context_mix": "jobs/L2/context.wav"},     // built by render from `hears`
        "params": {"track_name": "strings", "prompt": "soft sustained string pad, violas and cellos, no vibrato, slow, cinematic, no added vocals",
                   "repaint_start": 74.1, "repaint_end": 182.6, "guidance": 7, "variants": 4, "seed": null}
      },
      "hears": ["piano", "L1"],
      "automation": [{"type": "swell", "from": {"bar": 23, "beat": 1}, "to": {"bar": 25, "beat": 1}, "db": [-12, 0]}],
      "chosen_by": "creator",
      "status": "planned"
    },
    {
      "id": "L3", "name": "guitar", "class": "guitar", "kind": "take",
      "route": "take", "asset": "a2",         // from asset-catalog.json
      "anchors": {"enter": {"bar": 33, "beat": 1}, "exit": {"bar": 40, "beat": 4}},
      "t0": 146.0, "t1": 182.6, "hears": [], "chosen_by": "creator", "status": "planned"
    },
    {
      "id": "L4", "name": "brass", "class": "brass", "kind": "stub",
      "route": "stub", "reason": "creator undecided; placeholder keeps the Logic session complete",
      "anchors": {"enter": {"bar": 25, "beat": 1}, "exit": {"bar": 40, "beat": 4}},
      "t0": 110.2, "t1": 182.6, "hears": [], "chosen_by": "claude", "status": "planned"
    }
  ],

  "order": ["L1", "L2", "L3", "L4"],         // render order == conditioning order; a layer may only hear ids earlier in this list (or "piano")

  "open": {
    "questions": ["Chorus: strings from bar 25 (variant A) or from the top (variant B)? Bound A for now."],
    "unresolved_specs": ["tempo map bars 17–20 ambiguous — render will trust the map as-is unless confirmed"]
  },

  "export": {"target": "logic", "sr": 48000, "bit_depth": 24, "stem_prefix_numbering": true}
}
```

## Rules with teeth

- **`t0`/`t1` are a cache.** They are recomputed from anchors by `clock.py`
  on every build. If someone edits them by hand, `validate.py` fails
  (bar↔time inconsistency) and says which layer.
- **`hears` is acyclic and backward-looking.** A layer may hear `piano` and
  any layer that precedes it in `order`. This is how "vocal first, then strings
  that leave room for the voice" is expressed — and why conditioning order is
  an editorial decision made here, not a render default.
- **`chosen_by: creator` is authoritative.** Rebuilds use `--preserve
  old-arrangement.json`; a genuine conflict is raised once as a question.
- **Every layer leaves as exactly one stem.** `generated` renders, `take`
  copies (resampled/aligned), `stub` writes silence of the exact length. Parity
  in render refuses to ship if any layer has no stem.
- **Prompts are render-ready but still human.** They are written by plan from
  the notebook component text + class + the analysis (key, tempo, vibe), and
  shown in the tracks page so the creator can read what will be asked for.
  "no added vocals" is appended to every non-vocal audio-route job by default.
- **`job.inputs` paths under `jobs/` are produced by render**, not by plan
  (the context mix depends on stems that do not exist yet). Plan declares
  them; render materialises them.
