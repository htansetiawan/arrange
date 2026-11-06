# E2 revision suite — claude-sonnet-5-5, 3 draws per instruction and arm

Typed = the model answers with operations from the frozen vocabulary, applied deterministically. Free = the same model re-emits the whole edited plan JSON. Patch = the same model names paths and values to change (no re-emission). Same schema notes, same validator, same clock; derived seconds and ownership bookkeeping are excluded from the change counts. Recall and precision are over the JSON paths changed against the gold diff (expected operations applied to the frozen fixture). Collateral = paths changed outside the gold set. Stale = the set of layers marked for re-render matches the gold. Unsupported = for ambiguous or impossible requests, a visible question with no plan change. Protected = changes to fields the creator owns that the gold does not touch.

| id | fixture | instruction | arm | outcomes | recall | precision | collateral/draw | stale ok | unsupported ok | protected viol. | cost $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a1 | real | Bring the strings in two bars later. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| a1 | real | Bring the strings in two bars later. | free | applied, applied, applied | 1.00 | 0.17 | 152.3 | 3/3 | — | 24 | 0.16 |
| a1 | real | Bring the strings in two bars later. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.08 |
| a2 | synthetic | Let the chorus strings finish at the end of bar 38 instead of running to the end. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.01 |
| a2 | synthetic | Let the chorus strings finish at the end of bar 38 instead of running to the end. | free | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.16 |
| a2 | synthetic | Let the chorus strings finish at the end of bar 38 instead of running to the end. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.01 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | free | applied, applied, invalid | 0.67 | 0.44 | 0.7 | 2/3 | — | 0 | 0.22 |
| b1 | real | The strings should ignore the vocal and just follow the piano. | patch | applied, applied, applied | 0.67 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| b2 | synthetic | I want the guitar to hear the piano and the vocal only, not the strings. | typed | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.02 |
| b2 | synthetic | I want the guitar to hear the piano and the vocal only, not the strings. | free | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.16 |
| b2 | synthetic | I want the guitar to hear the piano and the vocal only, not the strings. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.07 |
| c1 | real | Use the second vocal take. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| c1 | real | Use the second vocal take. | free | applied, invalid, applied | 0.67 | 0.17 | 76.3 | 1/3 | — | 12 | 0.16 |
| c1 | real | Use the second vocal take. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.08 |
| c2 | synthetic | Go with the third strings option in the chorus. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| c2 | synthetic | Go with the third strings option in the chorus. | free | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.21 |
| c2 | synthetic | Go with the third strings option in the chorus. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| d1 | synthetic | Keep my guitar exactly as I played it, whatever else changes. | typed | no-op, no-op, no-op | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| d1 | synthetic | Keep my guitar exactly as I played it, whatever else changes. | free | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.21 |
| d1 | synthetic | Keep my guitar exactly as I played it, whatever else changes. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| d2 | synthetic | Drop the room fx and use my recorded guitar there instead. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| d2 | synthetic | Drop the room fx and use my recorded guitar there instead. | free | applied, applied, unresolved | 0.58 | 0.35 | 12.7 | 3/3 | — | 4 | 0.22 |
| d2 | synthetic | Drop the room fx and use my recorded guitar there instead. | patch | invalid, applied, applied | 0.06 | 0.27 | 3.0 | 3/3 | — | 6 | 0.09 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | typed | no-op, no-op, no-op | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | free | invalid, invalid, applied | 0.67 | 0.67 | 76.3 | 3/3 | — | 13 | 0.09 |
| e1 | real | Leave the brass out for now, just keep an empty track for it. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| e2 | synthetic | Put the brass back in, I want to hear it. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| e2 | synthetic | Put the brass back in, I want to hear it. | free | applied, applied, applied | 1.00 | 0.86 | 2.0 | 0/3 | — | 0 | 0.22 |
| e2 | synthetic | Put the brass back in, I want to hear it. | patch | applied, applied, applied | 1.00 | 0.84 | 2.3 | 0/3 | — | 0 | 0.08 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | typed | applied, unresolved, applied | 0.67 | 0.67 | 0.0 | 3/3 | — | 0 | 0.08 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | free | invalid, invalid, invalid | 0.00 | 0.00 | 0.0 | 3/3 | — | 0 | 0.12 |
| f1 | real | Bar 33 starts a beat late in your grid; the downbeat is where the bass lands, about half a second earlier. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 0/3 | — | 0 | 0.09 |
| f2 | synthetic | The downbeat of bar 17 is at 78.9 seconds, not where you put it. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.06 |
| f2 | synthetic | The downbeat of bar 17 is at 78.9 seconds, not where you put it. | free | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.23 |
| f2 | synthetic | The downbeat of bar 17 is at 78.9 seconds, not where you put it. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 0/3 | — | 0 | 0.08 |
| g1 | real | Make it more emotional. | typed | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.08 |
| g1 | real | Make it more emotional. | free | invalid, invalid, invalid | 1.00 | 1.00 | 0.0 | 3/3 | 0/3 | 0 | 0.09 |
| g1 | real | Make it more emotional. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.08 |
| g2 | synthetic | Move the strings a bit. | typed | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.07 |
| g2 | synthetic | Move the strings a bit. | free | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.22 |
| g2 | synthetic | Move the strings a bit. | patch | unresolved, unresolved, unresolved | 1.00 | 1.00 | 0.0 | 3/3 | 3/3 | 0 | 0.07 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | typed | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.07 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | free | invalid, applied, applied | 0.67 | 0.01 | 150.3 | 1/3 | — | 22 | 0.12 |
| h1 | real | Use the second vocal take and have the strings come in two bars later, hearing the piano only. | patch | applied, applied, applied | 1.00 | 1.00 | 0.0 | 3/3 | — | 0 | 0.09 |
| h2 | synthetic | Swap the verse strings for a guitar and bring it in at bar 20 instead of 17. | typed | applied, applied, unresolved | 0.67 | 0.67 | 0.0 | 2/3 | — | 0 | 0.08 |
| h2 | synthetic | Swap the verse strings for a guitar and bring it in at bar 20 instead of 17. | free | unresolved, applied, applied | 0.67 | 0.14 | 12.0 | 2/3 | — | 0 | 0.24 |
| h2 | synthetic | Swap the verse strings for a guitar and bring it in at bar 20 instead of 17. | patch | unresolved, applied, unresolved | 0.33 | 0.28 | 0.3 | 1/3 | — | 0 | 0.09 |

## Aggregates

| arm | instructions | mean recall | mean precision | collateral/draw | stale ok | unsupported ok | protected viol. | outcomes | cost $ |
|---|---|---|---|---|---|---|---|---|---|
| typed | 16 | 0.96 | 0.96 | 0.0 | 0.98 | 9/9 | 0 | applied 31, no-op 6, unresolved 11 | 1.01 |
| free | 16 | 0.81 | 0.61 | 30.2 | 0.81 | 6/9 | 75 | applied 26, invalid 11, unresolved 11 | 2.85 |
| patch | 16 | 0.88 | 0.90 | 0.4 | 0.77 | 9/9 | 6 | applied 30, invalid 1, unresolved 17 | 1.16 |

Caveats: draws are repeated samples of one model on one instruction, not independent tasks or users; the comparison is between two encodings of the same assistant, not between a system and a person; the fixtures and gold were frozen before any call (hashes in synthetic/FROZEN.sha256 and real/FROZEN.sha256).
