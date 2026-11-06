# Pilot ladder (ordered layout, the Median rule's key always on rung 4 of 6)

| voice | rule (median) | rule (top) | ear, canvas | ladder sweet | 'about right' band | strain 50 at | top note at sweet | = singer's own percentile | sweet on bottom rung |
|---|---|---|---|---|---|---|---|---|---|
| groban | -6 | -11 |  | **-10** | -10..-10 | -10.0 | E4 | 100 (clip only) | no |
| adams | +0 | -4 |  | **-4** | -6..-4 | -4.0 | A#4 | 100 | no |
| clarkson | +4 | +1 | +2 | **-2** | -2..+0 | -1.0 | C5 | 87 | yes, floor open |
| ariana | +4 | +0 | +2 | **-2** | -2..+0 | -1.2 | C5 | 91 | yes, floor open |
| jackson | -1 | -1 | -4 | **-7** | -7..-5 | -5.0 | G4 | 67 | yes, floor open |
| bolton | +1 | -1 | -4 | **-5** | -5..-5 | below ladder | A4 | 78 | yes, floor open |
| wonder | +2 | -3 | +2 | **-4** | -4..-2 | below ladder | A#4 | 99 | yes, floor open |
| buble | -6 | -9 | -8 | **-12** | -12..-10 | -12.0 | D4 | 89 | yes, floor open |

- Sweet minus median rule: [-4, -4, -6, -6, -6, -6, -6, -6] (mean -5.5); minus top rule: [1, 0, -3, -2, -6, -4, -1, -3] (mean -2.2); minus ear on the canvas: [-4, -4, -3, -1, -6, -4] (mean -3.7).
- Sweet spot on the bottom rung for 6/8 voices; floor closed by a 'too low' rung for 1/8. Strain steps per rung: groban [42, 50, 54, 61, 66, 75]; adams [44, 50, 59, 69, 80, 90]; clarkson [45, 55, 65, 75, 85, 95]; ariana [48, 53, 65, 75, 85, 95]; jackson [48, 50, 65, 75, 85, 95]; bolton [51, 57, 65, 75, 85, 95]; wonder [51, 53, 65, 75, 85, 95]; buble [50, 53, 60, 70, 80, 90].
- Top-anchor rule, leave one voice out (song's top note on the singer's own q-th percentile, q fitted on the other 7): groban q90 -14 (err -4), adams q90 -6 (err -2), clarkson q90 -2 (err +0), ariana q85 -3 (err -1), jackson q90 -4 (err +3), bolton q90 -4 (err +1), wonder q90 -6 (err -2), buble q85 -13 (err -1); mean abs error 1.8 vs median rule 5.5, top rule 2.5. (Lower bound where the floor is open.)

## Model key picks scored against the pilot (6 All the Things You Are cases; error = answer - pilot sweet spot)

| who | condition | mean abs error | mean signed | within ±2 | vs the composer's canvas keys (mean abs) |
|---|---|---|---|---|---|
| center.py | rule median | 6.0 | +6.0 | 0/6 | 2.3 |
| center.py | rule top | 3.2 | +3.2 | 2/6 | 2.5 |
| claude-haiku-5-5 | name | 3.8 | +3.8 | 9/18 | 2.9 |
| claude-haiku-5-5 | numbers | 5.0 | +5.0 | 1/18 | 1.8 |
| claude-haiku-5-5 | anon | 4.9 | +4.9 | 0/18 | 1.8 |
| claude-haiku-5-5 | image | 5.4 | +5.4 | 0/18 | 2.1 |
| claude-opus-5-5 | name | 5.2 | +5.2 | 2/18 | 2.9 |
| claude-opus-5-5 | numbers | 4.3 | +4.3 | 0/18 | 1.6 |
| claude-opus-5-5 | anon | 4.1 | +4.1 | 1/18 | 1.6 |
| claude-opus-5-5 | image | 4.6 | +4.6 | 1/18 | 2.0 |
| claude-sonnet-5-5 | name | 5.4 | +5.4 | 2/18 | 2.4 |
| claude-sonnet-5-5 | numbers | 4.9 | +4.9 | 0/18 | 1.7 |
| claude-sonnet-5-5 | anon | 4.7 | +4.7 | 0/18 | 1.6 |
| claude-sonnet-5-5 | image | 4.7 | +4.7 | 0/18 | 1.8 |
| gemma-4-31b-fp8 | name | 7.1 | +7.1 | 0/18 | 4.1 |
| gemma-4-31b-fp8 | numbers | 6.3 | +6.3 | 0/18 | 2.7 |
| gemma-4-31b-fp8 | anon | 6.4 | +6.4 | 0/18 | 2.7 |
| gemma-4-31b-fp8 | image | 5.1 | +5.1 | 3/18 | 2.6 |
| qwen3.5-27b-fp8 | name | 4.7 | +4.7 | 5/18 | 2.7 |
| qwen3.5-27b-fp8 | numbers | 4.1 | +4.1 | 4/18 | 1.8 |
| qwen3.5-27b-fp8 | anon | 3.7 | +3.7 | 5/18 | 1.8 |
| qwen3.5-27b-fp8 | image | 4.8 | +4.4 | 2/17 | 2.6 |
| gemma-4-e4b-it | hears the voice | 4.6 | +4.4 | 9/18 | 3.3 |
| qwen2.5-omni-7b | hears the voice | 6.4 | +6.3 | 6/18 | 5.6 |
