# E2-edits: the lyric skill installed as a Claude skill vs the same content in the prompt

Same items; skill = Claude Code with the skill installed; typed = notes, table and edits in the prompt (one turn); bare = raw rows. Paired by item over the items the skill arm has run; typed and bare use their first draws to match.

| model | items | skill | typed | bare | skill vs typed (items better/worse, sign-test p) | skill loaded | turns (median) | $ per try |
|---|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | 62 x 3 | 0.84 | 0.80 | 0.60 | 9/5, p = 0.424 | 172/186 | 5 | 0.005 |
| claude-opus-5-5 | 62 x 3 | 0.89 | 0.92 | 0.83 | 2/6, p = 0.289 | 186/186 | 5 | 0.153 |
| claude-sonnet-5-5 | 62 x 3 | 0.82 | 0.91 | 0.74 | 2/12, p = 0.013 | 186/186 | 5 | 0.070 |

By kind, skill / typed / bare:

- claude-haiku-5-5: list 0.67 / 0.67 / 0.56 (n=3); passage 0.78 / 0.94 / 0.56 (n=6); pattern 1.00 / 1.00 / 0.56 (n=3); question 1.00 / 1.00 / 0.50 (n=2); revision 1.00 / 1.00 / 0.67 (n=2); single 0.90 / 0.82 / 0.66 (n=39); symptom 0.48 / 0.43 / 0.33 (n=7)
- claude-opus-5-5: list 0.89 / 1.00 / 1.00 (n=3); passage 1.00 / 1.00 / 0.89 (n=6); pattern 1.00 / 1.00 / 1.00 (n=3); question 1.00 / 1.00 / 0.50 (n=2); revision 1.00 / 1.00 / 1.00 (n=2); single 0.93 / 0.93 / 0.85 (n=39); symptom 0.43 / 0.71 / 0.57 (n=7)
- claude-sonnet-5-5: list 0.67 / 0.78 / 1.00 (n=3); passage 0.94 / 1.00 / 0.83 (n=6); pattern 0.89 / 1.00 / 0.78 (n=3); question 1.00 / 0.83 / 0.50 (n=2); revision 1.00 / 1.00 / 1.00 (n=2); single 0.85 / 0.93 / 0.78 (n=39); symptom 0.52 / 0.71 / 0.33 (n=7)

Questions, pooled over the Claude models:

| arm | asked on complete requests | asked on incomplete requests |
|---|---|---|
| skill | 55/459 | 79/81 |
| typed | 31/459 | 77/81 |
| bare | 24/459 | 54/81 |
