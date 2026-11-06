# Verification: what `verify.py` measures on every candidate

Measurements are computed, never inferred from the prompt. `verify.py` writes
them per rendered candidate, each with its estimator and window. No thresholds
are applied and nothing is rejected: the numbers sit next to the creator's
choice, and the creator's ear decides.

| Measurement | Applies to | How |
|---|---|---|
| `chroma` | every rendered candidate | cosine similarity of the mean chroma (librosa `chroma_cqt`, hop 2048) of the candidate and the piano over the layer's window. Evidence about pitch-class content, not a certificate of harmony. |
| `level` | every rendered candidate | RMS in dB over the window, candidate minus piano |
| `pitch` | score-route vocals | share of pYIN frames within 100 cents of the score's note plus the candidate's shift (vibrato and portamento count against it) |
| `length` | every rendered candidate | exact sample count against the spine, checked by the backend on PCM before the MP3 is written (`frames_match_spine`) |
| `leak` | instrumental jobs | reported as unmeasured |

For a sung line, `/arrange-lyrics` adds two checks of its own: the entry of each
line (`mixcheck.py`, run by `sing.py`) and, across takes, the words Whisper does
not hear and the share of each note in tune (`check_takes.py`).

## Reading the numbers

- Low chroma similarity on every candidate of a layer usually means the prompt
  lacks the key or the context mix was too quiet for the model to hear the
  harmony: a plan problem.
- A sung line whose pitch share drops in the same bars on every take points at
  the fit (a note out of the singer's range, or too many syllables there): fix
  it in `/arrange-lyrics`.
- One candidate poor, the others fine: a seed. Render more takes if more
  choices are wanted.
