#!/usr/bin/env python3
"""analyze_posthoc.py: post hoc checks on the blind round (not in prereg.json; exploratory).

    python3 analyze_posthoc.py        # RESULT-posthoc.md (needs blind-joined.json from analyze_blind.py)

1. Each key choice scored by what the composer heard at that key: his mean strain there (linear between measured keys; beyond the
   measured range, the end key's value, marked) and his tag; works for all 8 voices, censored or not.
2. H1 by direction for all 8 voices: is the top-anchor key closer to the blind sweet spot than the median rule's?
   (censored voices: the sweet spot is below the lowest key, so any prediction above that key errs high by at least
   the gap.) Sign test.
3. Consistency: Spearman of strain with key per voice.
4. The models and the composer's own canvas keys scored the same way on the 6 All the Things You Are cases.
"""
import json, sys
from collections import defaultdict
from math import comb
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent; K = HERE.parent
pre = json.load(open(HERE / "prereg.json"))["voices"]
rows = json.load(open(HERE / "blind-joined.json"))
by = defaultdict(lambda: defaultdict(list))
for r in rows:
    by[r["voice"]][r["shift"]].append(r)
curve = {v: sorted((s, float(np.mean([x["strain"] for x in xs])), [x["register"] for x in xs]) for s, xs in d.items()) for v, d in by.items()}


def heard(v, k):
    c = curve[v]; sh = [s for s, *_ in c]
    if k <= sh[0]:
        return c[0][1], ("≤" if k < sh[0] else ""), c[0][2]
    if k >= sh[-1]:
        return c[-1][1], ("≥" if k > sh[-1] else ""), c[-1][2]
    for (s0, a, t0), (s1, b, t1) in zip(c, c[1:]):
        if s0 <= k <= s1:
            w = (k - s0) / (s1 - s0); return a + w * (b - a), "", (t0 if w < .5 else t1)


def sweet(v):   # blind sweet spot: first strain-50 crossing, else ('below', lowest key)
    c = curve[v]
    for (s0, a, _), (s1, b, _) in zip(c, c[1:]):
        if a <= 50 <= b and a != b:
            return s0 + (50 - a) / (b - a) * (s1 - s0), None
    return None, c[0][0] if c[0][1] > 50 else c[-1][0]


L = ["# Blind round, post hoc checks (exploratory; the frozen analysis is RESULT.md)", "",
     "## Strain the composer heard at each rule's key (≥ / ≤ = beyond the keys he heard; tag = his tag at the nearest key)", "",
     "| voice | top-anchor q90 | median rule | top rule | ear, canvas | pilot sweet | blind sweet (strain 50) | strain↔key Spearman |", "|---|---|---|---|---|---|---|---|"]
cols = ["top_anchor_q90", "rule_median", "rule_top", "ear_1nov", "ladder1_sweet"]
agg = defaultdict(list); closer = []
for v, p in pre.items():
    cells = []
    for c in cols:
        k = p.get(c)
        if k is None:
            cells.append(""); continue
        s, mark, tags = heard(v, k); agg[c].append((s, tags)); cells.append(f"{k:+d}: {mark}{s:.0f} {''.join(t[0] for t in tags)}")
    sw, floor = sweet(v)
    sw_txt = f"{sw:+.1f}" if sw is not None else f"below {floor:+d}"
    rho = spearmanr([s for s, *_ in curve[v]], [m for _, m, _ in curve[v]])[0]
    L.append(f"| {v} | " + " | ".join(cells) + f" | {sw_txt} | {rho:+.2f} |")
    ta, md = p["top_anchor_q90"], p["rule_median"]
    if sw is not None:
        closer.append((v, abs(ta - sw) < abs(md - sw)))
    else:   # sweet below `floor`: both predictions above floor -> compare distances to floor (lower bound)
        closer.append((v, ta < md))
L += ["", "Mean strain at the key (lower = less struggle; ~50 = a little tension) and share tagged about right:"]
for c in cols:
    if agg[c]:
        L.append(f"- {c}: mean strain {np.mean([s for s, _ in agg[c]]):.0f}; 'about right' {sum(t.count('right') / len(t) for _, t in agg[c]):.1f}/{len(agg[c])}; "
                 f"too high {sum(t.count('high') / len(t) for _, t in agg[c]):.1f}/{len(agg[c])}")
k = sum(c for _, c in closer); n = len(closer)
p1 = sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n
L += ["", f"H1 by direction, all voices: top-anchor closer than the median rule for {k}/{n} ({', '.join(v for v, c in closer if c)}); one-sided sign test p = {p1:.4f}."]
# models
gold6 = {"attya/" + v for v in ("buble", "jackson", "clarkson", "bolton", "ariana", "wonder")}
L += ["", "## Models' key picks scored by what the composer heard (6 All the Things You Are cases)", "",
      "| who | condition | mean strain at the pick | tagged about right | too high | mean pick − blind sweet (lower bound where censored) |", "|---|---|---|---|---|---|"]


def model_row(who, cond, picks):
    st, rt, hi, off = [], 0, 0, []
    for case, k in picks:
        v = case.split("/")[1]; s, _, tags = heard(v, k); st.append(s); rt += tags.count("right") / len(tags); hi += tags.count("high") / len(tags)
        sw, floor = sweet(v); off.append(k - (sw if sw is not None else floor))
    L.append(f"| {who} | {cond} | {np.mean(st):.0f} | {rt:.0f}/{len(picks)} | {hi:.0f}/{len(picks)} | {np.mean(off):+.1f} |")


for f in sorted((K / "llm/results").glob("*.json")):
    res = json.load(open(f))
    for cond in ("name", "numbers", "anon", "image"):
        picks = [(x["case"], x["shift"]) for x in res["rows"] if x["cond"] == cond and x["case"] in gold6 and x["shift"] is not None]
        if picks:
            model_row(res["model"], cond, picks)
for f in sorted((K / "llm/listen-results").glob("*.json")):
    res = json.load(open(f))
    picks = [(x["case"], x["shift"]) for x in res["rows"] if x["q"] == "key" and x["case"] in gold6 and x["shift"] is not None]
    if picks:
        model_row(res["model"], "hears the voice", picks)
for c, lab in (("top_anchor_q90", "rule top-anchor q90"), ("rule_median", "rule median"), ("ear_1nov", "the composer by ear on the canvas (sighted)")):
    model_row("center.py" if c != "ear_1nov" else "composer", lab, [(f"attya/{v}", pre[v][c]) for v in ("buble", "jackson", "clarkson", "bolton", "ariana", "wonder")])
(HERE / "RESULT-posthoc.md").write_text("\n".join(L) + "\n"); print("\n".join(L))
