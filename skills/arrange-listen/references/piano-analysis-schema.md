# `piano-analysis.json` — what `/arrange-listen` produces

The analysis is a **statement of facts about one recording**, each with a
provenance (`method`) and, where the fact came from a model, a confidence and
an `inspection` level. It never contains an opinion about what to add.

Every time-bearing fact is stated in **bars and beats first**; seconds are a
derived cache computed from `tempo_map` and are regenerated whenever the map
changes. This is the invariant the rest of the pipeline rests on: plan anchors
to `bar:beat`, render reads derived seconds, nobody else converts.

```json
{
  "schema": "arrange/piano-analysis@1",
  "source": {
    "path": "takes/piano_master.wav",
    "sha256": "…",
    "sr": 48000, "channels": 2, "dur_s": 214.31,
    "lufs_i": -18.4, "peak_dbfs": -1.2,
    "silence_lead_s": 0.42, "silence_tail_s": 3.10
  },
  "transcription": {
    "midi": "analysis/piano.mid",
    "tool": "bytedance-piano_transcription_inference", "version": "0.0.5",
    "notes": 1842, "pedal_events": 210,
    "confidence": "high",
    "inspection": "auto"            // auto | creator-checked
  },
  "tempo_map": {
    "method": "onsets+madmom-downbeat",   // or: tapped | click | creator-confirmed
    "time_signature": "4/4",
    "anacrusis_beats": 0,
    "beats": [ {"t": 0.42, "bar": 1, "beat": 1}, {"t": 1.61, "bar": 1, "beat": 2}, … ],
    "bpm_mean": 50.3, "bpm_min": 44.1, "bpm_max": 58.7,
    "rubato": "high",                      // low | medium | high — from local tempo variance
    "confidence": 0.71,
    "inspection": "auto",
    "unresolved": ["bars 17–20: downbeat ambiguous, two readings fit"]
  },
  "key": {
    "tonic": "F", "mode": "major", "confidence": 0.82,
    "modulations": [ {"bar": 33, "tonic": "Ab", "mode": "major", "confidence": 0.6} ]
  },
  "chords": [ {"bar": 1, "beat": 1, "chord": "Fmaj7", "confidence": 0.74}, … ],
  "sections": [
    {"id": "s1", "label": "intro", "bar_start": 1, "bar_end": 8,
     "t0": 0.42, "t1": 38.9, "source": "auto"},       // auto | creator
    {"id": "s2", "label": "verse 1", "bar_start": 9, "bar_end": 24, "t0": 38.9, "t1": 110.2, "source": "auto"}
  ],
  "melody": {
    "midi": "analysis/melody.mid", "abc": "analysis/melody.abc",
    "method": "skyline",                   // skyline | model:<name> | creator
    "range": {"low": "F4", "high": "C6"},
    "notes_per_section": {"s2": 28, "s3": 31},
    "inspection": "auto"
  },
  "dynamics": [ {"bar": 1, "rms_db": -28.1}, {"bar": 2, "rms_db": -27.4}, … ],
  "derived_at": "2026-10-30T14:02:11Z",
  "unresolved": [
    "time signature: 4/4 assumed; bars 17–20 could be 6/4",
    "melody: bars 41–44 ambiguous between right-hand voices"
  ]
}
```

## Rules

- `tempo_map.beats` is the **only** clock. It must cover the whole recording
  from the first downbeat to the last beat, with no gaps; `clock.py` in plan
  refuses a map with a gap larger than one beat and says which bars.
- `method` is honest. `tapped` (the creator tapped along) and
  `creator-confirmed` outrank any automatic method; a re-run of the automatic
  tracker never overwrites a creator-confirmed map.
- `sections` are a **proposal**. Brainstorm's cells may rename, split or merge
  them; the cell names in the notebook win, and plan reports the mapping.
- `unresolved` is a list of sentences in musical language ("downbeat ambiguous
  in bars 17–20"), never field names. Plan surfaces them to the creator before
  binding; render refuses to guess at anything still unresolved that a job
  needs.
- Nothing here is a recommendation. If `/arrange-listen` notices something worth
  saying ("the left hand already covers the bass register"), it goes in the
  conversation, not the file.
