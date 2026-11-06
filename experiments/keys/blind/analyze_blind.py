#!/usr/bin/env python3
"""analyze_blind.py: the blind round (one clip at a time, shuffled) against the frozen predictions (prereg.json) and the pilot.

    python3 analyze_blind.py          # RESULT.md and blind-joined.json (needs ../pilot/pilot-joined.json)

Primary per voice: the shift where the mean strain crosses 50 (linear between keys; 'below range' when every key is
above 50, 'above range' when every key is below). Repeats: first showing vs repeat. Broken clips are listed and
excluded from the crossing.
"""
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pilot"))
from analyze_pilot import crossing  # noqa: E402

key = json.load(open(HERE / "key.json")); pre = json.load(open(HERE / "prereg.json"))
L1 = {r["voice"]: r for r in json.load(open(HERE.parent / "pilot/pilot-joined.json"))}
rows = []
for f in sorted((HERE / "answers").glob("*.json")):
    d = json.load(open(f)); d = d.get("data", d); k = key[d["clip"]]
    rows.append({**k, "clip": d["clip"], "register": d["register"], "strain": d["strain"], "broken": d.get("broken", False), "at": d.get("at")})
json.dump(rows, open(HERE / "blind-joined.json", "w"), indent=1)
n_total = len(key)
by = defaultdict(lambda: defaultdict(list))
for r in rows:
    if not r["broken"]:
        by[r["voice"]][r["shift"]].append(r)

L = [f"# Blind round (one clip at a time, shuffled): {len(rows)}/{n_total} clips answered", "",
     "| voice | keys (strain, tag) low → high | strain 50 at | 'about right' band | pilot strain 50 / sweet | top-anchor q90 (frozen) | median rule |",
     "|---|---|---|---|---|---|---|"]
res = {}
for v in pre["voices"]:
    sh = sorted(by[v]); steps = [{"shift": s, "strain": float(np.mean([x["strain"] for x in by[v][s]]))} for s in sh]
    if not steps:
        continue
    c = crossing(steps)
    if c is None:
        c_txt = "below range" if steps[0]["strain"] > 50 else "above range"
    else:
        c_txt = f"{c:+.1f}"
    tags = {s: [x["register"] for x in by[v][s]] for s in sh}
    right = [s for s in sh if all(t == "right" for t in tags[s])]
    res[v] = {"strain50": c, "right": right}
    cells = " ".join(f"{s:+d}:{np.mean([x['strain'] for x in by[v][s]]):.0f}{''.join(t[0] for t in tags[s])}" for s in sh)
    p = pre["voices"][v]
    l1 = "below" if p["ladder1_strain50"] is None else f"{p['ladder1_strain50']:+.1f}"
    L.append(f"| {v} | {cells} | **{c_txt}** | {(f'{min(right):+d}..{max(right):+d}') if right else '-'} | {l1} / {p['ladder1_sweet']:+d} | {p['top_anchor_q90']:+d} | {p['rule_median']:+d} |")

def errs(rule):
    return [pre["voices"][v][rule] - res[v]["strain50"] for v in res if res[v]["strain50"] is not None]
L += [""]
for rule in ("top_anchor_q90", "rule_median", "rule_top"):
    e = errs(rule)
    if e:
        L.append(f"- {rule}: mean abs error to the strain-50 key {np.mean(np.abs(e)):.1f} (signed {np.mean(e):+.1f}), within ±2 on {sum(abs(x) <= 2 for x in e)}/{len(e)}")
both = [v for v in res if res[v]["strain50"] is not None and pre["voices"][v]["ladder1_strain50"] is not None]
if both:
    d = [res[v]["strain50"] - pre["voices"][v]["ladder1_strain50"] for v in both]
    L.append(f"- H2 blind minus pilot strain-50 key: " + ", ".join(f"{v} {x:+.1f}" for v, x in zip(both, d)) + f"; within 2 on {sum(abs(x) <= 2 for x in d)}/{len(d)}")
reps = defaultdict(list)
for r in rows:
    reps[(r["voice"], r["shift"])].append(r)
pairs = [(k, sorted(x, key=lambda r: r["pos"])) for k, x in reps.items() if len(x) == 2]
if pairs:
    L.append("- H3 repeats (first → repeat): " + "; ".join(f"{v} {s:+d}: {a['strain']}{a['register'][0]} → {b['strain']}{b['register'][0]}" for (v, s), (a, b) in pairs)
             + f"; mean |Δ| {np.mean([abs(a['strain'] - b['strain']) for _, (a, b) in pairs]):.1f}, same tag {sum(a['register'] == b['register'] for _, (a, b) in pairs)}/{len(pairs)}")
br = [r for r in rows if r["broken"]]
if br:
    L.append("- Marked broken: " + ", ".join(f"{r['voice']} {r['shift']:+d}" for r in br))
ts = sorted(r["at"] for r in rows if r.get("at"))
if ts:
    L.append(f"- Answered {ts[0]} to {ts[-1]}")
(HERE / "RESULT.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
