#!/usr/bin/env python3
"""analyze_side_by_side.py: the side-by-side ladder (sighted, ordered, voices anonymous). Its picks are the reference.
Compares each voice's ladder with the blind round and recheck (the same audio files), the pilot and the rules.

    python3 analyze_side_by_side.py   # RESULT.md and side-by-side-joined.json
                                       # (needs ../blind/blind-joined.json and ../recheck/recheck-joined.json)
"""
import json, glob
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent; R = HERE.parent
key = json.load(open(HERE / "key.json")); k1 = json.load(open(R / "pilot/key.json"))
pre = json.load(open(R / "blind/prereg.json"))["voices"]

def load(store, kk):
    out = {}
    for f in sorted(glob.glob(str(store / "*.json"))):
        d = json.load(open(f)); v = kk[d["steps"][0]["clip"]]["voice"]
        out[v] = dict(steps=[(kk[s["clip"]]["shift"], s["register"], s["score"]) for s in d["steps"]],
                      sweet=kk[d["sweet"]]["shift"] if d.get("sweet") else None)
    return out

L3, L1 = load(HERE / "answers", key), load(R / "pilot/answers", k1)
blind = defaultdict(lambda: defaultdict(list))
for f in (R / "blind/blind-joined.json", R / "recheck/recheck-joined.json"):
    for r in json.load(open(f)):
        blind[r["voice"]][r["shift"]].append((r["strain"], r["register"]))

def blind_sweet(v):   # first strain-50 crossing of the blind mean curve; else censored
    c = sorted((s, np.mean([x for x, _ in xs])) for s, xs in blind[v].items())
    for (s0, a), (s1, b) in zip(c, c[1:]):
        if a <= 50 <= b and a != b:
            return s0 + (50 - a) / (b - a) * (s1 - s0), ""
    return (c[0][0], "below") if c[0][1] > 50 else (c[-1][0], "above")

rows, lines = [], []
T = ["# Side-by-side ladder (sighted, ordered lowest to highest, 7-8 keys per voice, voices anonymous and shuffled)", "",
     "| voice | side-by-side sweet | rung (of n) | tags low→high | strain per rung | blind sweet (blind + recheck) | pilot sweet (rung) | top-anchor q90 | median rule |",
     "|---|---|---|---|---|---|---|---|---|"]
pairs = []; rung_pick = []
for v in pre:
    st = L3[v]["steps"]; sw = L3[v]["sweet"]; sh = [s for s, *_ in st]
    r = sh.index(sw) + 1; rung_pick.append(r)
    bs, cen = blind_sweet(v)
    s1 = L1[v]["sweet"]; r1 = [s for s, *_ in L1[v]["steps"]].index(s1) + 1
    T.append(f"| {v} | **{sw:+d}** | {r} of {len(st)} | {''.join(t[0] for _, t, _ in st)} | {' '.join(str(x) for *_, x in st)} | "
             f"{'below ' if cen == 'below' else ''}{bs:+.1f} | {s1:+d} ({r1}) | {pre[v]['top_anchor_q90']:+d} | {pre[v]['rule_median']:+d} |")
    for s, t, x in st:
        b = blind[v].get(s)
        rows.append(dict(voice=v, shift=s, rung=sh.index(s) + 1, register=t, strain=x, sweet=s == sw,
                         blind_strain=[y for y, _ in b] if b else None, blind_register=[y for _, y in b] if b else None))
        if b:
            pairs.append((v, s, x, float(np.mean([y for y, _ in b])), t, [y for _, y in b]))
json.dump(rows, open(HERE / "side-by-side-joined.json", "w"), indent=1)

# template: strain by rung position across voices
pos = defaultdict(list)
for v in pre:
    for i, (_, _, x) in enumerate(L3[v]["steps"]):
        pos[i + 1].append(x)
d = np.array([p[2] - p[3] for p in pairs])
same_tag = sum(p[4] in p[5] for p in pairs)                    # the ladder tag matches at least one blind answer
same_every = sum(all(t == p[4] for t in p[5]) for p in pairs)    # ... matches every blind answer (the paper's count)
rho_within = [spearmanr([p[2] for p in pairs if p[0] == v], [p[3] for p in pairs if p[0] == v])[0] for v in pre if sum(p[0] == v for p in pairs) >= 3]
ex = sorted(pairs, key=lambda p: p[2] - p[3])[:6]
T += ["",
      f"- Sweet spot sits on rung 4 for {rung_pick.count(4)}/8 voices, rung 3 for {rung_pick.count(3)}/8. Window floors were whichever lowest keys had been rendered, so rung 4 = floor + 6 semitones is not a property of the voices.",
      f"- Tags: {sum(''.join(t[0] for _, t, _ in L3[v]['steps']).count('r') == 2 for v in pre)}/8 voices have exactly two 'about right' rungs; the low→right→high switch is clean in all 8.",
      "- Strain by rung position, all voices (median): " + ", ".join(f"rung {k} {np.median(x):.0f}" for k, x in sorted(pos.items())) + ".",
      f"- Same audio, two layouts: {len(pairs)} clips were heard both blind (one at a time, shuffled) and on this ladder. "
      f"Ladder minus blind strain: mean {d.mean():+.0f}, mean |Δ| {np.abs(d).mean():.0f}; same tag as every blind answer {same_every}/{len(pairs)} (as at least one: {same_tag}); "
      f"within-voice rank agreement (Spearman, mean over voices) {np.mean(rho_within):+.2f}.",
      "- Largest drops (ladder far less strained than blind): " + "; ".join(f"{v} {s:+d}: blind {b:.0f} → ladder {x}" for v, s, x, b, *_ in ex) + ".",
      ]
l1 = [L3[v]["sweet"] - L1[v]["sweet"] for v in pre]
bl = [(v, L3[v]["sweet"] - blind_sweet(v)[0], blind_sweet(v)[1]) for v in pre]
ta = [L3[v]["sweet"] - pre[v]["top_anchor_q90"] for v in pre]; md = [L3[v]["sweet"] - pre[v]["rule_median"] for v in pre]
T += ["", "## Agreement", "",
      f"- With the pilot ladder (sighted, different windows): differences {l1}, mean |Δ| {np.mean(np.abs(l1)):.1f}.",
      "- With the blind sweet spot: " + ", ".join(f"{v} {x:+.1f}{' (blind censored below; lower bound)' if c == 'below' else ''}" for v, x, c in bl) +
      f"; mean {np.mean([x for _, x, _ in bl]):+.1f}.",
      f"- Top-anchor q90 rule vs this ladder: errors {[-x for x in ta]}, mean |Δ| {np.mean(np.abs(ta)):.1f}, signed {-np.mean(ta):+.1f}.",
      f"- Median rule vs this ladder: errors {[-x for x in md]}, mean |Δ| {np.mean(np.abs(md)):.1f}, signed {-np.mean(md):+.1f}."]
(HERE / "RESULT.md").write_text("\n".join(T) + "\n"); print("\n".join(T))
for p in sorted(pairs): print(p)
