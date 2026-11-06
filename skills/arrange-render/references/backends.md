# Backends: how each job runs

Two generating backends ship, under `scripts/backends/`. Each writes full-length,
zero-aligned candidates and a `candidates.json` that `register.py` records on the
plan. Where each model lives comes from the ARRANGE settings (`docs/setup.md`).

| Backend | Script | Job | How it is called | Notes |
|---|---|---|---|---|
| ACE-Step 1.5 | `backends/ace_step.py` | `ace-step/lego` (add one instrument layer) | Python API, offline; needs a **base** DiT (`acestep-v15-xl-base` by default); 50 steps, guidance 7, no LM planning, instrumental | Builds the layer's context exactly as the plan declares it (the piano plus the chosen candidate of every id in `conditions.audio_context`, each matched to the piano's RMS, -3 dB), runs Lego once per variant, keeps the plan's interval `[t0, t1)` with short fades. Records seeds, parents' hashes, elapsed time and peak memory. |
| SoulX-Singer | `backends/soulx.py` | `soulx-singer` (score-mode singing) | the SoulX-Singer CLI in score mode, from a sung score (one row per note: ARPAbet sounds, duration, MIDI pitch, note type sung / slur / rest) and a reference clip with its own metadata for the timbre. Options: `--n-steps`, `--cfg`, `--seed`, `--takes`, `--shifts` / `--pairs` | Normally run by `/arrange-lyrics` `sing.py`, which builds the sung score from the fit. The result is placed at the first note's time on the recording's clock. A sampler: the same score is a new take each render unless the seed is fixed; every candidate records its seed. |
| Stub | `stub.py` | `stub` | writes digital silence of the spine's exact length | always available |

Human takes are bound by the plan (`route: take`, an asset from
`asset-catalog.json`); `export.py` copies the file in.

## Length and alignment

Every result is trimmed or padded to exactly the spine's length, starting at
t = 0 of the recording, and the frame count is checked on PCM before the MP3
is written. Nothing needs positioning in the DAW.

## Failure policy

- Backend not installed → leave the layer a stub with a reason (`revise.py`
  `set_stub`); everything else renders. Render never switches backends.
- A failed variant is recorded as `failed` with its error; try another seed.
- Every variant poor in the same way → report it as a plan problem and name
  the likely cause (prompt, route, what the layer hears).
