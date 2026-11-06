# Craft notes for arrangement components

These are defaults a musician would recognise, not rules. The creator's ear
overrides all of them.

## Register — stay out of the melody's way

The analysis gives the melody's range (`melody.range`). A new layer that
lives in that range *doubles* or *fights* the tune. Doubling is a choice
("strings double the melody an octave up in the last chorus"); fighting is an
accident. Default sustained layers to **below the melody** (violas/cellos,
pads an octave down) unless the component says otherwise, and say which you
chose.

## One new thing per section

A listener hears an arrangement as *events*: the strings arriving, the voice
entering, the guitar joining. One event per section reads as shape; three
reads as clutter. When a cell wants two new layers, ask whether one of them
could enter in the next cell instead.

## Entries land on structure

Default an entry to the **downbeat of a phrase** (the analysis's section
start, or a bar where the chords return to the tonic). A layer entering mid-
phrase is a deliberate effect — mark it `!` if the creator asked for it,
otherwise prefer the phrase boundary and note the alternative.

## Swells, drops and exits are direction, not components

"Swell into the chorus", "drop out for two bars before the last verse",
"release at bar 40" go in the component's text or the cell's prose. Plan
turns them into automation hints and anchors; render applies them to the
stem. Don't invent a separate component for a dynamic gesture.

## The piano alone is a layer

Solo piano for a whole section is a legitimate arrangement decision, often
the right one for an intro or the last cell. Write it in prose ("piano alone,
let it breathe") so plan knows it was chosen, not forgotten.

## Vocals

- Keep `<lyrics>` verbatim. Report syllable/note mismatches as questions.
- The `<vocal>` component describes *who and how*: range, colour, intimacy,
  harmony on which line. Not the words.
- A sung verse over a piano that already plays the melody is a doubling;
  that is normal in a cover but say it once so the creator can decide to
  thin the right hand in the take or let the voice carry.

## When a section wants a variant

A real fork is structural: strings from the top vs. arriving at the chorus;
sung vs. instrumental; big ending vs. piano-alone ending. If both options
would be produced the same way and differ only in adjectives, it is not a
variant — pick one and move on.

## Reference tracks (Suno etc.)

Translate what they liked into musical statements: "the strings arrived
late and built slowly" → `<strings: … @bar 17>` with "slow swell" in the
text. Never transcribe or imitate the generated track itself; the arrangement
is theirs.
