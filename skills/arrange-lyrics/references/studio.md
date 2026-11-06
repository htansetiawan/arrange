# The studio: Play the Line and the Score Canvas

Two pages a composer uses without typing code. Both are built for a project
by one command as self-contained HTML files. They open locally in a browser,
or can be hosted; hosted as claude.ai artifacts they keep their address
across updates, and the recorder saves takes to the artifact's store.

```
python scripts/studio.py <project>/arrange-project.json [--start-bar N]
  -> <project>/studio/play-the-line.html   publish with capabilities {"db": {}}
  -> <project>/studio/score-canvas.html    publish plain
```

## The project file (`arrange-project.json`)

| key | what | example |
|---|---|---|
| `title` | the name the composer uses | "Evening Hymn, verse 1" |
| `recording` | the composer's recording, untouched | `takes/piano.wav` |
| `analysis_measured` | `/arrange-listen`'s measured map; the recorder's base grid | `plan/piano-analysis.json` |
| `analysis` / `analysis_tapped` | the map rebuilt from the composer's taps (written by `merge_take.py`) | `plan/piano-analysis.tapped.json` |
| `fit` | the current words-on-notes, one row per note (`fit-format.md`) | `plan/fit.json` |
| `chords` | optional chord-per-bar list | |
| `reference` | optional sung reference (a demo the composer likes), on the same clock | |
| `voice`, `voice_shift` | a folder under the configured `voices_dir`, or `english`; semitones | `myvoice`, `-12` |
| `window` | seconds of the recording the pages carry | `[0, 70]` |
| `build`, `studio` | output folders | |
| `voice_mix` | written by `sing.py`: the sung preview the canvas plays | |
| `pronounce` | optional: the composer's pronunciations, `{"word": ["sounds on note 1", ...]}` | `plan/pronounce.json` |
| `voice_take` | written by `sing.py`: the kept take (voice, shift, seed, steps, guidance) | |

Machine paths (Python environments, SoulX, voices) live in the ARRANGE
config (`config.example.json`, read from `$ARRANGE_CONFIG` or
`~/.config/arrange/config.json`) or `ARRANGE_*` environment variables, never in
a project. See `docs/setup.md` in the repository.

## Play the Line

- Start bar, count-in of two bars from the recording, a click on every beat
  of the composer's feel, the recording behind them.
- Computer keys (A = C … ' = F, Z/X octave) or the on-screen keys; touch works.
  A MIDI keyboard works through Web MIDI where the browser allows it; a hosted
  page's frame may block it (open the standalone copy then).
- Notes snap to quarters of the composer's beat on the grid and show as the composer's shorthand
  with bar lines, plus a piano roll; Play back checks a take.
- **Beat grid**: nudge 10 or 50 ms earlier or later; **Tap the beat** — tap T on
  every beat while it plays and the taps become the grid for those bars.
- Store (read by `/arrange-lyrics` with the artifact database tool):
  - `takes/<take-id>`: `saved_at`, `shorthand`, `words` (lines separated by `/`),
    `start_bar`, `start_t`, `notes` [{pitch, t, end, on, off}], `grid_offset_ms`, `taps`
  - `grid/current`: `offset_ms`, `taps` (seconds), `tapped_bars`, `saved_at`
- The page refuses to load twice (a live update must not double the key
  listeners) and ignores a repeat of the same key within 60 ms.

## Score Canvas

- The fit engraved by Verovio from MusicXML: bar numbers in the composer's tapped count on
  every bar, notes, the words (in blue: they are clickable), a number under each
  note within its line, the key's accidentals only, flat-side spellings in flat
  keys, bass clef when the line sits low. Chord names only when the project
  lists `chords`. No clock times on the staff.
- Click a note to hear the sung mix from there; voice pills switch between
  sung mixes; a checkbox turns the voice off; switch to the reference singer.
- Below the staff: the lines (start time, notated bar, words) and the sounds
  sent to the singer for each syllable.

## The round trip (what /arrange-lyrics does when the composer says "take saved")

1. Read `takes/` and `grid/current` from the recorder's store (newest take).
2. `python scripts/merge_take.py <project> --take <take.json> --grid <grid.json> [--words "line" ...]`
   — taps become the tempo map, the composer's lead is removed, doubled notes merge,
   fumbles are reported, and only the take's span of the fit is replaced.
   Notes without words stay grey: ask which words they carry; never guess.
3. `python scripts/sing.py <project>` — phonemes, the voice render, the entry
   check at every line start (an entry joined to the note before it is said
   so), the mix. Do not send a mix whose entries are off by more than 150 ms
   without saying so.
4. `python scripts/studio.py <project>` and republish both pages at their
   addresses. Tell the composer what changed in musical words.

## Voices

A voice is a folder under `voices_dir` with `prompt.wav` (a singing clip, 10 to
15 s), `prompt.json` (its note and phoneme labels, from SoulX's preprocessing
of the clip) and `CONSENT.txt` saying who agreed to what use. `sing.py`
refuses a voice without `CONSENT.txt`. A speaking clip makes a poor singer; ask
for a sung one. A clone of someone who has not agreed stays private.
