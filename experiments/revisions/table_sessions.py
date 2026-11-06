"""table_sessions.py — E2s table: chained sessions (2 sessions x 8 turns x draws) per model and arm -> sessions-results/TABLE.md"""
import json, glob
from pathlib import Path
E2 = Path(__file__).parent
ARMS = [("typed", "ARRANGE typed ops"), ("patch", "named edits (unchecked)"), ("free", "rewrite + ARRANGE notes"), ("bare", "rewrite, no ARRANGE")]
NOTE = "S2 turn 5 asks to move bar 33's downbeat half a second earlier; the plan does not contain bar 33's time (the beat map is not in the prompt), so no arm can hit it except by luck; asking is the reasonable answer. It costs every arm equally."
L = ["# E2s — chained revision sessions (S1 synthetic, S2 real; 8 turns each; the next turn starts from the arm's own output)", "",
     "| model | arm | sessions | turns done right | sessions ending exactly on gold | same, not counting the bar-33 beat-map turn (not answerable from the plan) | paths off gold at the end (mean) | composer decisions lost at the end | re-render needs missed | rejected turns | cost $ |",
     "|---|---|---|---|---|---|---|---|---|---|---|"]
for d in sorted((E2 / "sessions-results").glob("*/")):
    for arm, label in ARMS:
        R = [json.load(open(f)) for f in sorted(d.glob(f"S*-{arm}-d*.json"))]
        if not R:
            continue
        n = len(R)
        L.append(f"| {d.name} | {label} | {n} | {sum(r['turns_ok'] for r in R)}/{8 * n} | {sum(r['final_exact'] for r in R)}/{n} | {sum(not [p for p in r['turns'][-1]['drift'] if not p.startswith('piano-analysis')] for r in R)}/{n} | "
                 f"{sum(r['final_drift'] for r in R) / n:.1f} | {sum(len(r['composer_lost_final']) for r in R)} | {sum(len(r['stale_missed']) for r in R)} | "
                 f"{sum(r['rejected'] for r in R)}/{8 * n} | {sum(r['cost'] for r in R):.2f} |")
L += ["", NOTE]
(E2 / "sessions-results/TABLE.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
