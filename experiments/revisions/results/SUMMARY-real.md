# E2 revision suite — claude-sonnet-5-5, 3 draws per instruction and arm

Typed = the model answers with operations from the frozen vocabulary, applied deterministically. Free = the same model re-emits the whole edited plan JSON. Patch = the same model names paths and values to change (no re-emission). Same schema notes, same validator, same clock; derived seconds and ownership bookkeeping are excluded from the change counts. Recall and precision are over the JSON paths changed against the gold diff (expected operations applied to the frozen fixture). Collateral = paths changed outside the gold set. Stale = the set of layers marked for re-render matches the gold. Unsupported = for ambiguous or impossible requests, a visible question with no plan change. Protected = changes to fields the creator owns that the gold does not touch.

| id | fixture | instruction | arm | outcomes | recall | precision | collateral/draw | stale ok | unsupported ok | protected viol. | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a1 | real | Bring the strings in two bars later. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| a1 | real | Bring the strings in two bars later. | free | applied, applied, applied | 1.00 | 0.17 | 152.3 | 3/3 | — | 24 | 0.16 |
| a1 | real | Bring the strings in two bars later. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.08 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | free | applied, applied, invalid | 0.67 | 0.44 | 0.7 | 2/3 | — | 0 | 0.22 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | patch | applied, applied, applied | 0.67 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| c1 | real | Use the second vocal take. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| c1 | real | Use the second vocal take. | free | applied, invalid, applied | 0.67 | 0.17 | 76.3 | 1/3 | — | 12 | 0.16 |
| c1 | real | Use the second vocal take. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.08 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | typed | no-op, no-op, no-op | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | free | invalid, invalid, applied | 0.67 | 0.67 | 76.3 | 3/3 | — | 13 | 0.09 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | typed | applied, unresolved, applied | 0.67 | 0.67 | 0.0 | 3/3 | — | 0 | 0.08 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | free | invalid, invalid, invalid | 0.00 | 0.00 | 0.0 | 3/3 | — | 0 | 0.12 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 0/3 | — | 0 | 0.09 |
| g1 | real | Make it more emotional. | typed | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.08 |
| g1 | real | Make it more emotional. | free | invalid, invalid, invalid | 1.00 | 1.00 | 0.0 | 3/3 | 0/3 | 0 | 0.09 |
| g1 | real | Make it more emotional. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.08 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | free | invalid, applied, applied | 0.67 | 0.01 | 150.3 | 1/3 | — | 22 | 0.12 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.09 |

## Aggregates

| arm | instructions | mean recall | mean precision | collateral/draw | stale ok | unsupported ok | protected viol. | outcomes | cost $ |
|---|---|---|---|---|---|---|---|---|---|
| typed | 7 | 0.95 | 0.95 | 0.0 | 1.00 | 3/3 | 0 | applied 14, no-op 3, unresolved 4 | 0.52 |
| free | 7 | 0.67 | 0.35 | 65.1 | 0.76 | 0/3 | 71 | applied 10, invalid 11 | 0.98 |
| patch | 7 | 0.95 | 1.00 | 0.0 | 0.86 | 3/3 | 0 | applied 15, unresolved 6 | 0.55 |

Caveats: draws are repeated samples of one model on one instruction, not independent tasks or users; the comparison is between two encodings of the same assistant, not between a system and a person; the fixtures and gold were frozen before any call (hashes in synthetic/FROZEN.sha256 and real/FROZEN.sha256).
