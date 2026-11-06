---
name: arrange-lyrics
description: Change the sung line of a composer's song when the composer asks — which syllable falls on which note, a note's pitch or timing, the words, how a word is pronounced — on the fit shown on the score canvas. Use whenever the composer asks to change, fix, move, add or delete notes, words or syllables of the sung line, says something in it sounds wrong, comes in late or is not sung, refers to bars, beats or the grey numbers on the score canvas, sends a screenshot of the canvas, or asks what the singer sings.
---

# /arrange-lyrics — changing the sung line

A composer sings their words on a melody they played on piano, and looks at it on the SCORE CANVAS: the melody
engraved as a score with bar numbers, the syllable under each note, and a small grey number under each syllable.
The sung line is a FIT: one row per note of the melody. The project's fit is in `song/`.

## See the fit first

```
python3 .claude/skills/arrange-lyrics/scripts/show_fit.py
```

prints the fit as a table, the pronounce file and the sounds the singer gets now. How to read it:

- bar and beat are as the canvas shows them: when the composer says "bar 18 beat 2" he means the row at bar 18, beat 2.
  Beats are the composer's beats (in 4/4, four per bar; in 3/4, three); 2.5 is halfway through beat 2.
- no. is the grey number the canvas prints under each sung syllable: it counts the syllables of a line from 1 (a new
  line starts after a gap of a second or more). "note 23" means the syllable with grey number 23.
- t and end are seconds in the piano recording.
- kind is "note" (carries a syllable in text), "slur" (holds the previous syllable over another note; text "~"), or
  "unsung" (a piano note the voice does not sing; text "").
- word groups the syllables of one word (rows with the same word share it); the singer gets each syllable as sounds
  (ARPAbet from the CMU dictionary), the word's sounds split between its notes at the vowels.
- The composer can set the sounds of a word in a PRONOUNCE file: {"Footsteps": ["F UH1", "T S EH1 P S"]} (one entry per
  note of the word). An entry applies to every place the word is sung.
- The composer writes notes as C4, Bb4, F#4 and often in shorthand: "walls (G4 F4)" = the word sung over G4 then F4.

## Change it

```
python3 .claude/skills/arrange-lyrics/scripts/edit_fit.py '<JSON list of edits>'
```

applies the edits in order, all or nothing, and prints the fit as it is now. Row numbers are the idx column as it is
before this call; every edit in one call refers to those numbers. After a call the rows are renumbered.

```
{"op":"set","row":i, ...any of "text","kind","word","pitch" (e.g. "A4"),"t","end" (seconds)}
{"op":"move","row":i,"bar":b,"beat":x}      start this note at the canvas bar/beat; it keeps its length unless you
                                            also give "end" (seconds)
{"op":"shift","rows":[i,...],"by":s}        move these notes by s seconds (negative = earlier), start and end
{"op":"insert","after":i,"pitch":"G4","kind":"note","text":"...","word":"...","t":s,"end":s}
{"op":"delete","row":i}
{"op":"pronounce","word":"Footsteps","sounds":["F UH1","T S EH1 P S"]}
```

## The composer owns every placement

Change only what the composer asks for. If the request could mean more than one edit, or leaves out something the
edit needs, ask one short question instead of guessing, and make no edits. If the composer asks a question rather
than for a change, answer it and make no edits.
