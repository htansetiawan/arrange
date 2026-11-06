---
name: arrange-lyrics
description: Put a composer's words on a melody they play over their own piano recording, show it engraved on a Score Canvas, sing it in a chosen voice and check it. Use when someone wants to play a vocal line on keys over a recording and tap the beat, fit lyrics to the notes they played, see and correct which syllable falls on which note or how a word is pronounced, make a singing voice from a recording they have consent for, choose the key a copied voice sings comfortably, render the sung line with SoulX-Singer, check where each sung line enters, or hear the voice mixed over the piano. Produces lyric-fit.json (one row per note), the Play the Line and Score Canvas pages, a sung track and a mix preview. The composer owns every placement; the agent proposes, applies typed edits and asks.
---

# /arrange-lyrics

This skill covers three steps of the ARRANGE chain, plus the entry check of the mix:

Listen (`/arrange-listen`) → **Play the Line → Fit → Sing** → Mix (`/arrange-render`)

- **Play the Line**: the composer plays the melody on keys over the recording and taps the beat.
- **Fit**: the words go under the notes, one syllable per note, with the sounds the singer gets for each syllable.
- **Sing**: a voice from a short reference clip sings the approved fit in a key it sings comfortably; each
  line's entry is measured against the score.

The fit is a musical decision at the level of the single note, so it is something the composer reads and
corrects directly, not a parameter the agent tunes. The agent never passes a checkpoint for the composer.

Setup: the scripts find Python environments, SoulX-Singer and the voices through the ARRANGE config or
`ARRANGE_*` environment variables (`config.example.json`; `docs/setup.md` in the repository). Install the
ARRANGE skills side by side: several scripts import `clock.py` from `/arrange-plan`.

## The studio: two pages, four commands

Read `references/studio.md` before the first use. For a project with an `arrange-project.json`:

```
python scripts/studio.py arrange-project.json [--start-bar N]                       # build Play the Line + Score Canvas
python scripts/merge_take.py arrange-project.json --take T --grid G [--words "line" ...]   # after "take saved"
python scripts/center.py --voice <voices_dir>/NAME --song <the project's fit> --audition 5   # the key, before singing
python scripts/sing.py arrange-project.json [--voice NAME --shift -12] [--try]      # the sung preview, entries checked
```

Both pages are self-contained HTML files in `<project>/studio/`. They can be opened locally. When they are
hosted as claude.ai artifacts, publish `play-the-line.html` with `capabilities: {"db": {}}` (takes and the beat
grid are saved to its store: `takes/`, `grid/current`) and `score-canvas.html` plain, and republish to the same
addresses on later rounds. Without hosting, the recorder downloads each take as a JSON file.

## Play the Line

The composer picks a bar, hears two bars of the recording as a count-in, and plays the line on the computer
keyboard, the on-screen keys or a MIDI keyboard while the recording plays. **Tap the beat** turns their taps into
the bar grid. After "take saved", `merge_take.py` runs `take.py`: the taps become the tempo map, the composer's
lead against their own taps is measured and removed, doubled notes merge, fumbles are reported, and only the
take's span of the fit is replaced. Notes without words stay grey: ask which words they carry; never guess.

## Fit

`take.py` lays the words one syllable per note. A line with more syllables than notes gets a note split in two at
the same pitch (first the first note, then the last); if words still do not fit, the report names the unsung
words. Notes beyond the words stay unsung for the composer to fill.

The singer gets each syllable as sounds (ARPAbet from the CMU dictionary, `phonemes.py`), cut between notes at the
longest onset English allows (mor-ning, not mo-rning). The Score Canvas shows these sounds under each line, so a
complaint such as "it feels choppy" can be traced to a syllable.

## Change the fit

When the composer asks for a change to the sung line (a syllable on another note, a note's pitch or timing, the
words, how a word is pronounced), look at the fit first, then apply typed edits:

```
python scripts/show_fit.py arrange-project.json [--no-sounds]
python scripts/edit_fit.py arrange-project.json '<JSON list of edits>'
```

`show_fit.py` prints the fit as a table, the pronounce file and the sounds the singer gets now. How to read it:

- `bar.beat` is as the canvas shows it, in the composer's count: "bar 18 beat 2" is the row at 18.2; 2.5 is
  halfway through beat 2.
- `no.` is the grey number the canvas prints under each sung syllable: syllables of a line counted from 1 (a new
  line starts after a gap of a second or more). "line 2, note 5" is the row whose `no.` is 5 in the second line.
- `t - end` are seconds in the recording. `kind` is `note` (carries a syllable), `slur` (holds the previous
  syllable over another note; text `~`) or `unsung` (a note the voice does not sing).
- `word` groups the syllables of one word. The composer writes notes as C4, Bb4, F#4, often in shorthand:
  "walls (G4 F4)" is the word sung over G4 then F4.

`edit_fit.py` applies the edits in order, all or nothing, and prints the fit as it is now. Row numbers are the
`idx` column as it was before the call; after a call the rows are renumbered.

```
{"op":"set","row":i, ...any of "text","kind","word","pitch" (e.g. "A4"),"t","end" (seconds)}
{"op":"move","row":i,"bar":b,"beat":x}      start this note at the canvas bar/beat; it keeps its length unless
                                            "end" (seconds) is also given
{"op":"shift","rows":[i,...],"by":s}        move these notes by s seconds (negative = earlier)
{"op":"insert","after":i,"pitch":"G4","kind":"note","text":"...","word":"...","t":s,"end":s}
{"op":"delete","row":i}
{"op":"pronounce","word":"Footsteps","sounds":["F UH1","T S EH1 P S"]}
```

The composer owns every placement: ask one short question instead of guessing. Change only what was asked. If a
request could mean more than one edit, or leaves out something the edit needs, ask and make no edits. If the
composer asks a question rather than for a change, answer it and make no edits. After edits, run `sing.py` and
`studio.py` again and say what changed in musical words.

## Saying a word the composer's way

When a join still sounds chopped, the composer can set the split of a word's sounds across its notes: a
`pronounce` file named in the project, `{"Footsteps": ["F UH1", "T S EH1 P S"]}` (one entry per note of the word;
vowels take a stress digit, 1 then 0, added if left off). Here the dictionary split "F UH T | S T EH P S" put two
stops at the join and sounded like "foot ^ steps"; one T, carried onto the second note, sings as one word. The
`pronounce` edit above writes this file (and adds it to the project if it has none). The entry applies wherever
the word is sung. The canvas's sounds list shows the split in force.

## Sing

### A voice from a recording

A zero-shot singer copies the sound of a short reference clip, so the clip decides most of the quality.
`make_voice.py` fetches the audio, separates the voice from the band, transcribes notes and words (SoulX's
preprocessing), ranks every 8-15 s stretch between breaths (`pick_prompt.py`: least band underneath, mostly sung,
held notes, near the range of the line it will sing) and makes the best one the voice, with the runners-up as
`<name>-clip2`, `-clip3` to compare.

```
python scripts/make_voice.py myvoice --source my_singing.m4a --consent "<name>, own voice; <allowed use>" \
    --project arrange-project.json --shift -12
```

- **Consent is required.** `--consent` is written to CONSENT.txt; `--private` marks a singer who has not agreed:
  private listening only, never a public page or a paper. `sing.py` refuses a voice folder without CONSENT.txt.
  Use only recordings you have the right to use.
- **Read what it heard.** A transcript with the right words means a clean reference; a garbled one (a language
  SoulX does not know, a loud band) means the clip will sound worse. SoulX knows English, Mandarin and Cantonese.

### The key: a rule proposes, the ear decides

Before the first render in a new voice, run the key rule and read all of its output:

```
python scripts/center.py --voice <voices_dir>/NAME --song <the project's fit> --audition 5
```

- Use **Top note** (`topnote`, the default, printed as "recommended") as the default key: it puts the song's
  highest note on the singer's 90th-percentile note.
- Print the other three rules for the composer as `center.py` gives them (`top`, `median`, `clip`), with one line
  each on what they line up (`references/keys.md`).
- Offer keys around it to hear: the `audition` keys (2 semitones apart around Top note) and the "topnote to top"
  span, where the composer's choice most often lay. The composer picks by ear; their pick wins.

The shift is what the voice sings relative to the written melody; `center.py` splits it into a piano key and an
octave. An octave alone needs no change to the piano: `sing.py arrange-project.json --voice NAME --shift <octave>`.
Any other key moves the piano too:

```
python scripts/transpose.py arrange-project.json --for-voice NAME --semitones <key> --octave <octave>
python scripts/sing.py arrange-project.key<key>-NAME.json --n-steps 64 --try    # transpose.py prints the file name
```

For another shift S to audition, the piano key is ((S + 6) mod 12) - 6 and the octave is S minus that key.

### Render, takes and seeds

```
python scripts/sing.py arrange-project.json --voice NAME --shift -12 --n-steps 64 --try
python scripts/sing.py arrange-project.json --voice NAME --shift -12 --takes 3
python scripts/check_takes.py --score <build>/sung-score.json --take a:-12:<take1.mp3> --take b:-12:<take2.mp3>
python scripts/sing.py arrange-project.json --voice NAME --shift -12 --seed <its seed>
```

- `--n-steps 64` is SoulX's highest-quality setting (32 is its default): slower, finer.
- `--try` renders for listening only and leaves the project's current voice alone.
- SoulX samples, so every render is a new take: the same sounds and notes, but how long each sound lasts inside a
  note and when the consonants land change, most on fast runs. `--takes 3` renders three takes and prints each
  one's seed and a ready `check_takes.py` command (words missed by Whisper, share of each note in tune). Keep one
  with `--seed <its seed>`; the project records it as `voice_take`, and later runs with that voice and key reuse
  it. A changed fit gives a different take even with the same seed.
- `convert_voice.py` re-voices a sung track in another singer's sound (SoulX's voice conversion), for a reference
  whose words SoulX cannot transcribe.

### The entry check

`sing.py` runs `mixcheck.py` on every render: for each line start it reports where the voice actually enters
(`ENTRY: 'word' score 12.40 s, voice 12.43 (+30 ms)`), writes `entries.json`, and mixes the voice +6 dB over the
piano on the sung stretch. An entry joined to the note before it (same pitch, no gap) is said so. Do not send a mix
whose entries are off by more than 150 ms without saying so.

## Other ways in

Playing the line is the way in that worked best: the keyboard gives pitch and rhythm in one pass. These remain for
material that already exists, each writing rows in the same fit format:

```
# from a sung reference (a demo, a scratch vocal): SoulX preprocessing, run in the SoulX-Singer folder, then notate.py
python -m preprocess.pipeline --audio_path reference.mp3 --save_dir reference-pre --language English --device cuda --vocal_sep True --midi_transcribe True
python scripts/notate.py --metadata reference-pre/metadata.json --analysis piano-analysis.json --window 64 118 --lyrics lyrics.txt -o jobs/L1/auto
python scripts/hear.py --reference reference.mp3 --analysis piano-analysis.json --window 64 118 -o jobs/L1/heard.json   # Demucs + pYIN instead
# from a written line and the words
python scripts/align.py --abc-notes written-line.json --midi piano.mid --analysis piano-analysis.json --window 70 116 -o jobs/L1/melody.json
python scripts/fit.py --melody jobs/L1/melody.json --lyrics lyrics.txt [--lines 1 4] -o jobs/L1/lyric-fit.json
# from the melody inside the piano, laid from a chosen slot
python scripts/skeleton.py --analysis piano-analysis.json --midi piano.mid --bars 1 8 -o jobs/skeleton-1-8 [--lyrics lines.txt]
python scripts/lay.py --skeleton jobs/skeleton-1-8/skeleton.json --analysis piano-analysis.json --start-slot 1 --lines lines.txt -o jobs/verse1
# dictated: a start, pitches by name and the words; or new pitches on the same beats
python scripts/dictate.py --score jobs/verse1/lyric-fit.json --analysis piano-analysis.json --script lines.dictated -o jobs/verse1
python scripts/repitch.py --score jobs/verse1/lyric-fit.json --analysis piano-analysis.json --from-word Quiet --pitches "E4 D4 C4 C4 D4 E4 F4" -o jobs/verse1
# a timeline editor page; its saved lyric-fit.edited.json is applied verbatim (only phonemes are computed)
python scripts/editor.py --fit jobs/L1/lyric-fit.json --audio piano-excerpt.mp3 --audio-start 68 -o lyric-editor/index.html
python scripts/fit.py --melody jobs/L1/melody.json --lyrics lyrics.txt --edits lyric-fit.edited.json -o jobs/L1/lyric-fit.json
```

`examples/lyric-fit.edited.example.json` is a small synthetic edit file. `fit.py` and `phonemes.py` need g2p_en;
`notate.py`, `canvas.py`, `skeleton.py`, `lay.py`, `dictate.py` and `repitch.py` need music21 and verovio.

## What you own

- **The fit**, `lyric-fit.json`: one row per note with start, end, pitch, the syllable (or `~` for a hold, empty
  for unsung), the word it belongs to and where the row came from. Read `references/fit-format.md`.
- **The pages**: Play the Line and the Score Canvas (`studio.py`).
- **Applying the composer's edits exactly**: by row (`edit_fit.py`) or a saved edit file (`fit.py --edits`).
  Nothing is re-fitted behind their back.
- **The sung preview and its entry check** (`sing.py`, `mixcheck.py`).

You own no arrangement decision, no choice of voice or key (you propose, the composer picks), and no seconds that
do not come from the performance or the composer's taps.

## Refuse to guess

| Situation | What you do |
|---|---|
| A note has no words after a take | Ask which words it carries; leave it grey until then |
| A line has more syllables than notes | Report the unsung words by name; offer a split or ask which word to drop |
| An edit request could mean two different edits | Ask one short question; make no edit |
| An edit breaks something mechanical (a note ends before it starts) | `edit_fit.py` refuses the whole call; say which row |
| A voice folder has no CONSENT.txt | `sing.py` refuses; ask who agreed and for what use |
| An entry is off by more than 150 ms | Say so with the word and the offset before sending the mix |

## The contract

This skill owns the performed line, the fit, the pages, the sung preview and the exact application of the
composer's edits. `sing.py` reads the fit from the project directly; `/arrange-plan` schedules layers in its own
plan and does not read `lyric-fit.json`. `/arrange-render` owns the finished mix (`polish.py`) and the DAW export.
