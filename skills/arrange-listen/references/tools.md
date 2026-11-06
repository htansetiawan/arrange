# Tools behind /arrange-listen: what each stage is good at, and the fallback

Two scripts: `transcribe.py` (the model) and `analyze.py` (every measured
stage, in one pass, from the MIDI and the audio). A corrected MIDI or a
creator-supplied fact re-runs `analyze.py` only.

| Stage | Script | Method | Good at | Weak at | Fallback |
|---|---|---|---|---|---|
| Transcription | `transcribe.py` | ByteDance `piano_transcription_inference` (Kong et al.): note F1 0.968 on MAESTRO, pedal events | clean solo piano, pedalled playing | non-piano timbres, heavy room, two instruments | a MIDI the creator fixed by hand, passed to `analyze.py --midi`; separate the piano first if the take is not solo |
| Probe | `analyze.py` | soundfile: sr, channels, length, lead/tail silence, sha256 | - | - | - |
| Tempo map | `analyze.py` | librosa beat tracking on an onset envelope built from the **transcription onsets**, bass-weighted downbeat phase; per-beat support from nearby played notes | expressive piano where audio-based trackers drift | fermatas, extreme rubato, silent bars | `--bpm` from the creator; the creator's taps in Play the Line (`/arrange-lyrics`, `take.py`, method `creator-tapped`); `--confirmed` after listening to `--click` |
| Key | `analyze.py` | Krumhansl profiles on duration-weighted pitch classes | diatonic material | modulating or chromatic passages | the creator states the key |
| Sections | `analyze.py` | a proposal: eight-bar phrases, plus theme statements at `--theme-at` times | regular phrase lengths | through-composed pieces | `--sections "label:a-b,..."` (source `creator`); brainstorm's cells win anyway |
| Melody | `analyze.py` | skyline (highest note per onset cluster), bar:beat positions | right-hand melody over accompaniment | inner-voice melodies, two-voice textures | list ambiguous bars; the creator plays the line in Play the Line |
| Dynamics | `analyze.py` | per-bar RMS in dB | - | - | - |

## Why onsets, not audio, for the beat

A slow, pedalled solo piano has almost no transient energy between the
hammer strikes, so spectral-flux beat trackers drift or lock onto harmonics.
Kong's transcription gives the hammer strikes directly, at millisecond
resolution; turning them into a click track and tracking *that* is both more
robust and more explainable ("the downbeat is where the left hand lands").

## Honesty rules

- Every stage writes `method` and, when a model produced the fact, a
  `confidence`. Downstream reads both.
- A creator-supplied fact (`tapped`, `creator-confirmed`, `creator-checked`,
  `source: creator`) is never overwritten by re-running the automatic stage.
- A stage that cannot produce its fact emits the field with `unresolved`
  text rather than a guess. Plan knows what to do with that; render refuses
  to guess.
