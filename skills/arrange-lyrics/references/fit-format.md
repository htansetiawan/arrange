# `lyric-fit.json` — one row per note, the composer's placements

```json
{
  "melody": "jobs/L1/melody.json",         // the performed line this fit sits on
  "lyrics": "lyrics.txt",                  // or lyric-fit.edited.json when a composer's edit was applied
  "lines": ["Quiet lanterns light the hill", "..."],
  "edited": true,                          // present when the rows came from the composer's edit
  "report": ["applied the creator's edit of <edited_at>: 8 notes ...", "..."],
  "rows": [
    {"index": 0, "t": 2.0, "end": 2.5, "pitch": 64, "bar": 2, "beat": 1.0,
     "text": "Qui", "word": "Quiet", "phoneme": "en_K-W-AY1", "kind": "note"},
    {"index": 2, "t": 3.0, "end": 3.25, "pitch": 60, "text": "lan", "word": "lanterns", "phoneme": "en_L-AE1-N",
     "kind": "note", "placed": "split by the composer"},
    {"index": 3, "t": 3.25, "end": 3.5, "pitch": 60, "text": "terns", "word": "lanterns", "phoneme": "en_T-ER0-N-Z", "kind": "note",
     "placed": "split by the composer"},
    {"index": 7, "t": 5.5, "end": 6.5, "pitch": 64, "text": "~", "word": "hill", "phoneme": "en_HH-IH1-L", "kind": "slur"},
    {"index": 8, "t": 7.0, "end": 7.5, "pitch": 62, "text": "", "phoneme": "", "kind": "unsung"}
  ]
}
```

Rules:

- `t` and `end` are seconds in the recording, from the performance; `bar` and
  `beat` are derived from the measured map and are for reading, not editing.
- `kind` is `note` (carries a syllable), `slur` (holds the previous syllable;
  `text` is `~`), or `unsung`.
- `word` groups the syllables of one word so phonemes can be split across its
  notes; a whole word on one note is fine (singing models sing it on one note).
- `placed` says where the row came from: `performance` (the transcription),
  `interpolated` (a written note the piano did not play), or `split by the
  composer` / `merged by the composer`.
- A composer's `lyric-fit.edited.json` has the same rows plus `edited_at`,
  `note` (their words to the next render) and `lines`; `fit.py --edits` copies
  the rows as they are and computes only `phoneme`.
  `examples/lyric-fit.edited.example.json` is a small synthetic one.
- Downstream: `/arrange-render`'s SoulX backend reads `rows` directly (text,
  phoneme, pitch, start, duration; `~` → note type 3; unsung → `<SP>`).
