# Blind round, post hoc checks (exploratory; the frozen analysis is RESULT.md)

## Strain the composer heard at each rule's key (≥ / ≤ = beyond the keys he heard; tag = his tag at the nearest key)

| voice | top-anchor q90 | median rule | top rule | ear, canvas | pilot sweet | blind sweet (strain 50) | strain↔key Spearman |
|---|---|---|---|---|---|---|---|
| groban | -14: 46 r | -6: 54 r | -11: 49 r |  | -10: 55 r | -10.8 | +0.14 |
| adams | -6: 75 h | +0: 88 h | -4: 90 h |  | -4: 90 h | below -8 | +0.81 |
| clarkson | -2: 45 l | +4: 97 h | +1: 87 h | +2: 90 h | -2: 45 l | -5.6 | +0.96 |
| ariana | -2: 80 h | +4: 92 h | +0: 80 hh | +2: 85 h | -2: 80 h | -3.8 | +0.95 |
| jackson | -4: 68 h | -1: 75 h | -1: 75 h | -4: 68 h | -7: 45 l | -4.9 | +0.95 |
| bolton | -4: 87 hh | +1: 89 h | -1: 88 h | -4: 87 hh | -5: 86 h | below -9 | +1.00 |
| wonder | -6: 90 h | +2: 90 h | -3: 83 hh | +2: 90 h | -4: 85 h | below -8 | +0.68 |
| buble | -12: 45 l | -6: 70 h | -9: 52 h | -8: 56 h | -12: 45 l | -9.3 | +0.96 |

Mean strain at the key (lower = less struggle; ~50 = a little tension) and share tagged about right:
- top_anchor_q90: mean strain 67; 'about right' 1.0/8; too high 5.0/8
- rule_median: mean strain 82; 'about right' 1.0/8; too high 7.0/8
- rule_top: mean strain 75; 'about right' 1.0/8; too high 7.0/8
- ear_1nov: mean strain 79; 'about right' 0.0/6; too high 6.0/6
- ladder1_sweet: mean strain 66; 'about right' 1.0/8; too high 4.0/8

H1 by direction, all voices: top-anchor closer than the median rule for 8/8 (groban, adams, clarkson, ariana, jackson, bolton, wonder, buble); one-sided sign test p = 0.0039.

## Models' key picks scored by what the composer heard (6 All the Things You Are cases)

| who | condition | mean strain at the pick | tagged about right | too high | mean pick − blind sweet (lower bound where censored) |
|---|---|---|---|---|---|
| claude-haiku-5-5 | name | 76 | 0/18 | 16/18 | +5.3 |
| claude-haiku-5-5 | numbers | 82 | 0/18 | 18/18 | +6.4 |
| claude-haiku-5-5 | anon | 82 | 0/18 | 18/18 | +6.4 |
| claude-haiku-5-5 | image | 84 | 0/18 | 18/18 | +6.8 |
| claude-opus-5-5 | name | 84 | 0/18 | 18/18 | +6.7 |
| claude-opus-5-5 | numbers | 81 | 0/18 | 18/18 | +5.7 |
| claude-opus-5-5 | anon | 81 | 0/18 | 18/18 | +5.5 |
| claude-opus-5-5 | image | 82 | 0/18 | 18/18 | +6.0 |
| claude-sonnet-5-5 | name | 83 | 0/18 | 18/18 | +6.8 |
| claude-sonnet-5-5 | numbers | 82 | 0/18 | 18/18 | +6.4 |
| claude-sonnet-5-5 | anon | 82 | 0/18 | 18/18 | +6.1 |
| claude-sonnet-5-5 | image | 82 | 0/18 | 18/18 | +6.2 |
| gemma-4-31b-fp8 | name | 85 | 0/18 | 18/18 | +8.5 |
| gemma-4-31b-fp8 | numbers | 86 | 0/18 | 18/18 | +7.8 |
| gemma-4-31b-fp8 | anon | 86 | 0/18 | 18/18 | +7.8 |
| gemma-4-31b-fp8 | image | 79 | 0/18 | 17/18 | +6.5 |
| qwen3.5-27b-fp8 | name | 80 | 0/18 | 17/18 | +6.2 |
| qwen3.5-27b-fp8 | numbers | 80 | 0/18 | 17/18 | +5.5 |
| qwen3.5-27b-fp8 | anon | 81 | 0/18 | 18/18 | +5.1 |
| qwen3.5-27b-fp8 | image | 80 | 0/17 | 15/17 | +5.7 |
| gemma-4-e4b-it | hears the voice | 77 | 0/18 | 16/18 | +5.8 |
| qwen2.5-omni-7b | hears the voice | 80 | 0/18 | 17/18 | +7.7 |
| center.py | rule top-anchor q90 | 69 | 0/6 | 4/6 | +1.8 |
| center.py | rule median | 86 | 0/6 | 6/6 | +7.4 |
| composer | the composer by ear on the canvas (sighted) | 79 | 0/6 | 6/6 | +5.1 |
