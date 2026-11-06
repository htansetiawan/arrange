# Choosing the key: four options and how they agreed with a composer's ear

`scripts/center.py` prints four candidate keys for a voice. None of them is the answer: the composer hears the
candidates and decides. This note records how each option compared with one composer's ear, so the options can be
weighed. The full study is in the paper (Section 5.5).

`center.py` uses `topnote` by default because it agreed most with the ear. The default is a starting point for
listening, not a verdict: no rule is right for every voice, and the method below matters more than the winner.

## How it was measured

1. **The problem.** Keys the composer first chose by ear on the canvas were lower than the earlier default
   (`median`) for 5 of 6 voices. On paper the median keys looked reasonable, because the rule matches the middle of
   the song to the middle of the singer and never looks at the top note.
2. **Pilot ladder.** Each voice at 6 keys, lowest at the bottom, the rule's guess always on the same rung. The sweet
   spots sat on the bottom rung for 6 of 8 voices: every rule was too high, and the ladder had not gone low enough.
   Because the guess was always on the same rung, the layout could teach a pattern, so it served as a pilot only.
   From it one number was chosen for a new rule: put the song's highest note on the singer's 90th-percentile note
   (picked by leaving each voice out in turn).
3. **Blind test, written down first.** The predictions and the test were frozen in a file before listening. Then 60
   clips, one at a time, all voices and keys shuffled, no names, with 6 clips repeated to measure how steady a single
   judgement is. Result: `topnote` closer than `median` for all 8 voices.
4. **The listener's scale.** Strain was rated 0 to 100: 98-100 screaming, 85-88 the border, 75 high but not cracking,
   about 50 the sweet spot, 30 too low. A short retest showed some takes are strained on their own (a bad take, not
   a bad key) and that one judgement can swing by about 10 points.
5. **Side by side (the reference).** Ears compare better than they judge one sound alone, so each voice's lowest 7-8
   keys were stacked, voices anonymous. These picks agreed with the pilot ladder within 2 semitones for all 8 voices
   and are the reference in the table below.
6. **Every layout pointed the same way:** `median` too high, `topnote` closest. The exact key moved by a few semitones
   between layouts, so the table is about which rule is closer, not about one perfect key.

## Why `topnote` works, and when it does not

- **Strain lives on the top note.** The sweet spot is where the voice does not struggle to hit the highest note; a
  little tension is good. The rule that looks at the highest note matches what the ear listens for. `median` looks at
  the middle of the song and cannot see a top note that is out of reach.
- **The singer's 90th-percentile note is high but everyday.** Only 1 in 10 of their sung notes go above it, so it is
  a note they reach often and comfortably, not their limit. Aiming the song's peak there leaves the little tension of
  a real high note without pushing to the edge.
- **Reference clips sit high** because they are usually choruses, so `clip` reads the singer as higher than they are.
- **When it misses (a guess, not yet tested).** It reads the singer from one recording. If that recording is showy,
  its high notes are higher than the singer's comfort, and `topnote` lands too high (two voices, 3 semitones). If the
  recording is restrained, it lands too low (one voice, 4). That is why the script still prints the other rules and
  offers keys around the default to hear.

## The four options

| option | what it lines up | in one sentence |
|---|---|---|
| `topnote` | song's highest note ↔ singer's 90th-percentile note | Can the singer reach the top note without straining? |
| `top` | song's high notes (top 10%) ↔ singer's high notes, as close to `median` as allowed | Lower the key only as far as the high passages need. |
| `median` | middle of the song ↔ middle of the singer's range | Sing it where the singer usually sings. |
| `clip` | middle of the song ↔ middle of the 10-second reference clip | Older rule; reference clips are usually choruses and sit high. |

## Agreement with the ear (one song excerpt, 8 voices)

Reference = the composer's sweet spot with the keys side by side: the key where the voice sings cleanly and
comfortably, with a little tension on the top note and no screaming. Error = option minus reference, in semitones;
+ = too high. Voices are anonymous (six male, two female; copied zero-shot by SoulX-Singer).

| voice | reference | topnote | top | median | clip |
|---|---|---|---|---|---|
| V1 | −10 | −14 (−4) | −11 (−1) | −6 (+4) | −6 (+4) |
| V2 | −6 | −6 (0) | −4 (+2) | 0 (+6) | 0 (+6) |
| V3 | −2 | −2 (0) | +1 (+3) | +4 (+6) | +6 (+8) |
| V4 | −2 | −2 (0) | 0 (+2) | +4 (+6) | +5 (+7) |
| V5 | −7 | −4 (+3) | −1 (+6) | −1 (+6) | −5 (+2) |
| V6 | −7 | −4 (+3) | −1 (+6) | +1 (+8) | 0 (+7) |
| V7 | −6 | −6 (0) | −3 (+3) | +2 (+8) | +2 (+8) |
| V8 | −10 | −12 (−2) | −9 (+1) | −6 (+4) | −4 (+6) |
| **mean miss** | | **1.5** | 3.0 | 6.0 | 6.0 |
| **lean** | | none | +2.8 | +6.0 | +6.0 |
| **within 2 semitones** | | 5/8 | 4/8 | 0/8 | 1/8 |
| **exact** | | 4/8 | 0/8 | 0/8 | 0/8 |

- `topnote` agrees most often and does not lean either way. It was exact for 4 of 8 voices.
- `top` is closest for V1 and V8; `clip` is closest for V5.
- `median` and `clip` were too high for every voice. This matches the strain heard at the median-rule keys in the
  blind test: mean strain 82 there, against 67 at `topnote`.
- No option fits every voice. V5 and V6 liked keys 3 below `topnote`; V1 liked a key 4 above it.
  For 5 of 8 voices the reference fell between `topnote` and `top`, so auditioning that span is a good start
  (`center.py` prints it as "topnote to top").

## Caveats

- One listener, one song excerpt (15 s around its highest note, D5), synthetic voices.
- The ladder layout pulls picks toward the middle of the keys shown. The blind one-at-a-time test put five voices
  2–4 semitones lower; the ordering of the options was the same in both.
- Language models asked to pick the key were 4–7 semitones too high on the same cases.
