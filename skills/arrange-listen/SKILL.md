---
name: arrange-listen
description: Analyze a recorded solo piano take and produce piano-analysis.json, the measured facts the rest of ARRANGE anchors to - transcribed MIDI (Kong's piano transcription), a tempo map from the transcription's onsets (bar:beat to seconds, rubato-aware, with uncertain bars listed), the key, a proposed section layout, a skyline melody and per-bar dynamics, plus a click track to confirm the beats. Use whenever someone has a piano recording they want to add a voice or instruments to, wants the key, tempo or bar grid measured, wants it transcribed, or asks whether a recording is ready to be layered. First step of the ARRANGE chain. Produces facts with provenance only, never a suggestion about what to add.
---

# /arrange-listen

The first step of the ARRANGE chain:

**Listen** (`/arrange-listen`) → Play the Line, Fit, Sing (`/arrange-lyrics`) → Plan (`/arrange-brainstorm`, `/arrange-plan`) → Mix (`/arrange-render`)

You take the composer's **piano recording** (the spine of everything that
follows) and produce **`piano-analysis.json`**, the measured facts every later
step anchors to. Read `references/piano-analysis-schema.md` before writing it;
it is the shared contract and you own producing it.

Your job is **listening and measuring**, not arranging. Which instruments to
add, where, how: that is `/arrange-brainstorm`'s conversation with the composer.
If you notice something worth saying ("your left hand already owns the bass
register"), say it in the chat; it does not go in the file.

The recording exists before the plan does, so the clock is *measured* from the
start. Everything downstream anchors to bar:beat in the tempo map you produce,
so get the tempo map right before anything else.

## Opening move

Ask for the recording and, in the same message, two things:

1. **Time signature and feel**, if they know it ("4/4, very rubato, ~50
   BPM"). A human's answer outranks the tracker's guess and goes into the map
   as `creator-confirmed`.
2. **Any other takes** that belong to this piece (a guitar pass, a hummed
   melody, a scratch vocal). Note them for `/arrange-plan`, which can bind a
   layer to a human take from an asset catalogue instead of generating it.

Then start. Don't interview.

## The tempo map is the whole game

Solo piano played expressively does not have a BPM; it has a **tempo map**:
a list of beat times with bar and beat numbers. Where a layer enters, where
the vocal's syllables fall and where the DAW puts bar lines all come from this
map. A wrong map disguises itself as an editorial problem later (strings that
"enter late", a vocal that "rushes"), so:

- Track the beat from the **transcription onsets**, not from the raw audio.
  Piano onsets from Kong's transcription are far cleaner beat evidence than a
  spectral-flux curve on a slow, pedalled recording. `analyze.py` does this.
- Report `rubato` (low / medium / high) and the bars with weak support, in bar
  language: "bars 17–20: no played note near a tracked beat". They are in
  `tempo_map.unresolved`. Never smooth them away.
- Give the composer the click track (`--click`) to check the beats by ear. If
  the map is wrong, the best fix is the composer's own taps: Play the Line in
  `/arrange-lyrics` has **Tap the beat**, and `take.py` turns the taps into a
  `creator-tapped` map. A mean tempo the composer states goes in as `--bpm`.
- A map the composer has tapped or confirmed (`creator-tapped` /
  `creator-confirmed`) is **never overwritten** by a re-run of the tracker.

## Workflow

```
python scripts/transcribe.py takes/piano.wav -o analysis/piano.mid [--device cpu]     # Kong piano transcription (+pedal)
python scripts/analyze.py    takes/piano.wav --midi analysis/piano.mid -o analysis/ \
                             [--time-sig 4/4] [--bpm 52] [--sections "verse:9-24,chorus:25-40"] \
                             [--click analysis/click.mp3 --click-window 0 60] [--confirmed]
```

`transcribe.py` needs `piano_transcription_inference` and torch; its checkpoint
downloads on first use (see `docs/setup.md`). `analyze.py` needs librosa,
pretty_midi and soundfile; it takes an existing MIDI as given, so a MIDI the
composer fixed by hand can replace the transcription. Re-run it with
`--confirmed` once the composer has listened to the click track and agreed.
See `references/tools.md` for what each stage is good and bad at.

## What "done" looks like

Deliver three things and stop:

1. **`piano-analysis.json`**, and the click track if one was made.
2. **A one-screen summary in musical language**: key, meter, mean tempo and
   range, rubato level, the proposed sections with bar ranges, the melody's
   range, and the `unresolved` list verbatim. No field names.
3. **The questions** the unresolved items raise — asked once, as choices
   ("bars 17–20 read as either 4/4 with a fermata or one bar of 6/4 — which
   did you play?"). Their answer re-runs `analyze.py` with the correction, marked
   `source: creator`.

Then hand off: "Next, play the line you want sung over the recording
(`/arrange-lyrics`), or say what you hear on top (`/arrange-brainstorm`)."

## Refuse to guess

| Situation | What you do |
|---|---|
| Transcription confidence is low (dense pedal, wrong instrument, heavy noise) | Say so, set `confidence: low`, still emit the file. Offer the creator the MIDI to hand-fix and mark it `creator-checked` on re-run. |
| Tempo tracker finds no stable grid | Emit the map with `confidence` low and the gaps listed; recommend tapping the beat in Play the Line. Never fabricate beats to fill a gap. |
| Two voices compete for "the melody" | Pick the skyline (highest sounding) and list the ambiguous bars under `unresolved`. The creator decides; plan asks. |
| The recording is not solo piano (voice + piano, band) | You can still run; set `transcription.tool` accordingly and say the melody extraction and key will be less reliable. Vocals in the source should be noted — plan will need to know the register is occupied. |
| The creator asks "what should I add?" | That is `/arrange-brainstorm`. Answer briefly in conversation if they insist, but do not put it in the file. |

## The contract (see references/responsibility-matrix.md)

This skill owns the transcription, the tempo map, the key, the section
*proposal*, the melody line and the dynamics curve, every one a fact with
provenance. It owns no arrangement decision, no prompt, no model choice, and
no seconds that are not derived from its own map.
