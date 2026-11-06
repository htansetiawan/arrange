#!/usr/bin/env python3
"""paper_numbers.py: every number in Section 5.5 of the paper ("Choosing the key"), from the stored answers, keys and
model outputs in this folder. No model, no audio, no network. Needs numpy.

    python3 paper_numbers.py

Each line gives the paper's claim, then the value computed here.
"""
import json
from collections import defaultdict
from math import comb
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V = ["groban", "adams", "clarkson", "ariana", "jackson", "bolton", "wonder", "buble"]
SIX = ["buble", "jackson", "clarkson", "bolton", "ariana", "wonder"]          # the voices also keyed by ear on the canvas
RULES = ["topnote", "top", "median", "clip"]
NAME = {"topnote": "Top note", "top": "Top", "median": "Median", "clip": "Clip"}
load = lambda p: json.load(open(HERE / p))

prof = load("data/profiles.json"); pre = load("blind/prereg.json")
rule = {v: prof["rules"][f"attya/{v}"] for v in V}


def show(section, claim, value):
    print(f"[{section}] {claim}\n    -> {value}")


def answers(folder):
    return [json.load(open(f)) for f in sorted((HERE / folder / "answers").glob("*.json"))]


def ladder(folder):
    """Per voice: the picked key and the keys shown (low to high) with tag and strain."""
    key = load(f"{folder}/key.json"); out = {}
    for d in answers(folder):
        steps = [(key[s["clip"]]["shift"], s["register"], s["score"]) for s in d["steps"]]
        out[key[d["steps"][0]["clip"]]["voice"]] = {"sweet": key[d["sweet"]]["shift"], "steps": steps}
    return out


def checks(folder):
    key = load(f"{folder}/key.json")
    return [{**key[d["clip"]], "clip": d["clip"], "strain": d["strain"], "register": d["register"], "broken": d.get("broken", False)}
            for d in answers(folder)]


def crossing(curve):
    """Key where the mean strain crosses 50, linear between keys; None if it never crosses."""
    for (s0, a), (s1, b) in zip(curve, curve[1:]):
        if a <= 50 <= b and a != b:
            return s0 + (50 - a) / (b - a) * (s1 - s0)
    return None


pilot, side = ladder("pilot"), ladder("side-by-side")
blind, recheck = checks("blind"), checks("recheck")
ref = {v: side[v]["sweet"] for v in V}                       # the reference: the side-by-side picks

# ---------------------------------------------------------------- opening paragraph
low = [v for v in SIX if pre["voices"][v]["ear_1nov"] < rule[v]["median"]]
show("5.5", "the composer's first keys by ear were lower than the obvious rule (Median) for 5 of 6 voices", f"{len(low)} of 6 ({', '.join(low)})")
err = {r: np.array([rule[v][r] - ref[v] for v in V]) for r in RULES}
show("5.5", "Top note matched the composer within 1.5 semitones on average, with no lean",
     f"mean miss {np.abs(err['topnote']).mean():.2f}, mean signed {err['topnote'].mean():+.2f}")
show("5.5", "Median was 6 semitones too high for every voice",
     f"mean signed {err['median'].mean():+.2f}; too high for {(err['median'] > 0).sum()} of 8 (per voice {list(map(int, err['median']))})")

# ---------------------------------------------------------------- LLMs (computed first; the opening paragraph cites them)
gold6 = {f"attya/{v}": ref[v] for v in SIX}
llm = {}
for f in sorted((HERE / "llm/results").glob("*.json")):
    res = json.load(open(f))
    for cond in ("name", "numbers", "anon", "image"):
        e = [r["shift"] - gold6[r["case"]] for r in res["rows"] if r["cond"] == cond and r["case"] in gold6 and r["shift"] is not None]
        llm[(res["model"], cond)] = (round(float(np.mean(np.abs(e))), 1), float(np.mean(e)))
listen = {}
for f in sorted((HERE / "llm/listen-results").glob("*.json")):
    res = json.load(open(f))
    e = [r["shift"] - gold6[r["case"]] for r in res["rows"] if r["q"] == "key" and r["case"] in gold6 and r["shift"] is not None]
    listen[res["model"]] = (round(float(np.mean(np.abs(e))), 1), float(np.mean(e)))
allm = [a for a, _ in llm.values()] + [a for a, _ in listen.values()]
show("5.5", "LLMs asked the same question were 4 to 7 semitones too high",
     f"mean miss per model and condition {min(allm)} to {max(allm)}; signed error > 0 in every case: "
     f"{all(s > 0 for _, s in list(llm.values()) + list(listen.values()))}")

# ---------------------------------------------------------------- what the skill measures
src = {v: prof["voices"][v]["source"] for v in V}
show("5.5", "the singer's pitch is read from the whole separated recording; for Groban only the clip was available",
     "; ".join(f"{v}: {s}" for v, s in src.items()))
show("5.5", "the song's highest note is D5", f"highest written note MIDI {prof['songs']['attya']['high']} (D5 = 74)")

# ---------------------------------------------------------------- how the ear was asked
n = {d: len(load(f"{d}/key.json")) for d in ("pilot", "blind", "recheck", "side-by-side", "groban-recheck")}
show("5.5", "he heard 185 clips in three rounds (48; 60 + 14; 63)",
     f"pilot {n['pilot']}, blind {n['blind']} + recheck {n['recheck']}, side by side {n['side-by-side']}: "
     f"{n['pilot'] + n['blind'] + n['recheck'] + n['side-by-side']} (the named Groban recheck, {n['groban-recheck']} clips, reused side-by-side audio and is not counted)")
k1 = load("pilot/key.json")
rungs = {v: len(pilot[v]["steps"]) for v in V}
pred_rung = {k1[d["steps"][0]["clip"]]["voice"]: [k1[s["clip"]]["offset_from_pred"] for s in d["steps"]].index(0) + 1 for d in answers("pilot")}
show("5.5 pilot", "six keys per voice; the rule's key always sat on the same rung",
     f"keys per voice {sorted(set(rungs.values()))}; rung of the Median rule's key {sorted(set(pred_rung.values()))}")
bottom = [v for v in V if pilot[v]["sweet"] == min(s for s, *_ in pilot[v]["steps"])]
show("5.5 pilot", "sweet spots fell on the lowest key for 6 of 8 voices", f"{len(bottom)} of 8")
# leave one voice out: q (30..95) that best fits the other seven pilot picks, rule = round(voice q-th percentile - song's top note)
pct = {v: prof["voices"][v]["percentiles_1_to_99"] for v in V}; top = prof["songs"]["attya"]["high"]
qs = list(range(30, 100, 5))
fold_q = [min(qs, key=lambda q: sum(abs(round(pct[o][q - 1] - top) - pilot[o]["sweet"]) for o in V if o != v)) for v in V]
show("5.5 pilot", "the percentile was chosen on the pilot, leaving one voice out at a time (90th)",
     f"q chosen per fold {fold_q}; 90 in {fold_q.count(90)} of 8 folds; frozen rule: {pre['rule'][:60]}...")
rep = [r for r in blind if r["repeat"]]
show("5.5 blind", "60 clips with 6 repeats, then a 14-clip recheck", f"{len(blind)} answers, {len(rep)} repeats; recheck {len(recheck)} answers")
t_first = min(d["at"] for d in answers("blind"))
show("5.5 blind", "the predictions and hypotheses were frozen in a file before listening", f"prereg.json frozen_at {pre['frozen_at']}; first answer {t_first}")
k3 = load("side-by-side/key.json")
per = defaultdict(int)
for c in k3.values(): per[c["voice"]] += 1
show("5.5 side by side", "63 clips: each voice's 7 to 8 lowest keys", f"{len(k3)} clips; keys per voice {dict(per)}")

# ---------------------------------------------------------------- which rule agrees with the ear
e = err["topnote"]
show("5.5 rules", "Top note missed by 1.5 on average with no lean, exactly right for 4 of 8, within 2 for 5",
     f"{np.abs(e).mean():.2f}, lean {e.mean():+.2f}, exact {(e == 0).sum()} of 8, within 2 {(np.abs(e) <= 2).sum()} of 8")
for r in ("top", "median", "clip"):
    show("5.5 rules", f"{NAME[r]} missed by {'3.0' if r == 'top' else '6.0'}, too high on average",
         f"{np.abs(err[r]).mean():.2f}, mean signed {err[r].mean():+.2f}")
show("5.5 rules", "Median was too high for every voice", f"{(err['median'] > 0).sum()} of 8")
# blind round, post hoc: Top note closer than Median to the blind sweet spot, for every voice
by = defaultdict(lambda: defaultdict(list))
for r in blind: by[r["voice"]][r["shift"]].append(r["strain"])
curve = {v: sorted((s, float(np.mean(x))) for s, x in d.items()) for v, d in by.items()}


def heard(v, k):          # strain the composer heard at key k (linear between keys heard; end value beyond them)
    c = curve[v]
    if k <= c[0][0]: return c[0][1]
    if k >= c[-1][0]: return c[-1][1]
    for (s0, a), (s1, b) in zip(c, c[1:]):
        if s0 <= k <= s1: return a + (k - s0) / (s1 - s0) * (b - a)


closer = []
for v in V:
    sw = crossing(curve[v]); ta, md = pre["voices"][v]["top_anchor_q90"], pre["voices"][v]["rule_median"]
    closer.append(abs(ta - sw) < abs(md - sw) if sw is not None else ta < md)   # no crossing: sweet spot below every key heard
k = sum(closer); p1 = sum(comb(8, i) for i in range(k, 9)) / 2 ** 8
show("5.5 rules", "blind round: Top note closer than Median for all 8 voices (one-sided sign test p = 0.004, added after the frozen hypotheses)",
     f"{k} of 8, one-sided p = {p1:.4f}")
st = {c: np.mean([heard(v, pre["voices"][v][c]) for v in V]) for c in ("top_anchor_q90", "rule_median")}
show("5.5 rules", "strain at Top note's keys averaged 67 against 82 at Median's", f"{st['top_anchor_q90']:.1f} against {st['rule_median']:.1f}")
h1 = [(v, crossing(curve[v])) for v in V if crossing(curve[v]) is not None]
show("5.5 rules", "(frozen H1, for reference) mean miss to the strain-50 key on the voices with a crossing",
     f"{len(h1)} voices: Top note {np.mean([abs(pre['voices'][v]['top_anchor_q90'] - c) for v, c in h1]):.1f}, "
     f"Median {np.mean([abs(pre['voices'][v]['rule_median'] - c) for v, c in h1]):.1f}")
best = {v: [NAME[r] for r in RULES if abs(rule[v][r] - ref[v]) == min(abs(rule[v][x] - ref[v]) for x in RULES)] for v in V}
show("5.5 rules", "Top was closest for Groban and Bublé, Clip for Jackson", "; ".join(f"{v}: {'/'.join(b)}" for v, b in best.items()))
btw = [v for v in V if min(rule[v]["topnote"], rule[v]["top"]) <= ref[v] <= max(rule[v]["topnote"], rule[v]["top"])]
show("5.5 rules", "for 5 of 8 voices the reference lay between Top note and Top, ends included", f"{len(btw)} of 8 ({', '.join(btw)})")

# ---------------------------------------------------------------- what the layout changed
d1 = [ref[v] - pilot[v]["sweet"] for v in V]
show("5.5 layout", "side-by-side picks agreed with the pilot within 2 semitones for all 8 voices", f"{sum(abs(x) <= 2 for x in d1)} of 8 (differences {d1})")
pooled = defaultdict(lambda: defaultdict(list))
for r in blind + recheck: pooled[r["voice"]][r["shift"]].append(r["strain"])
lower = {}
for v in V:
    c = sorted((s, float(np.mean(x))) for s, x in pooled[v].items()); x = crossing(c)
    gap, note = (ref[v] - x, "") if x is not None else (ref[v] - c[0][0], " (at least; strain above 50 at every key heard)") if c[0][1] > 50 else (None, "")
    if gap is not None and gap >= 1.5: lower[v] = f"{gap:.1f}{note}"
show("5.5 layout", "the blind round put 5 voices 2 to 4 semitones lower", f"{len(lower)} voices: " + "; ".join(f"{v} {g}" for v, g in lower.items()))
side_tag = {(k3[s["clip"]]["voice"], k3[s["clip"]]["shift"]): (s["register"], s["score"]) for d in answers("side-by-side") for s in d["steps"]}
both = [(kv, side_tag[kv], [(r["register"], r["strain"]) for r in blind + recheck if (r["voice"], r["shift"]) == kv]) for kv in side_tag]
both = [b for b in both if b[2]]
dd = [s[1] - np.mean([x for _, x in bl]) for _, s, bl in both]
every = sum(all(t == s[0] for t, _ in bl) for _, s, bl in both); anyt = sum(s[0] in [t for t, _ in bl] for _, s, bl in both)
show("5.5 layout", "the same 52 audio files heard both ways were rated 7 points less strained side by side, and kept their tag in 33 of 52",
     f"{len(both)} files; side by side minus blind strain {np.mean(dd):+.1f}; same tag as every blind answer {every} of {len(both)} "
     f"(as at least one blind answer: {anyt})")
reps = defaultdict(list)
for r in blind: reps[(r["voice"], r["shift"])].append(r)
pairs = [sorted(x, key=lambda r: r["pos"]) for x in reps.values() if len(x) == 2]
show("5.5 layout", "one judgement moved by about 9 points when repeated, and 5 of 6 repeats kept their tag",
     f"mean |difference| {np.mean([abs(a['strain'] - b['strain']) for a, b in pairs]):.1f}; same tag {sum(a['register'] == b['register'] for a, b in pairs)} of {len(pairs)}")
rp = {r["clip"]: r for r in load("data/render-pitch.json")}
for v, s, nb in (("clarkson", -4, (-6, -2)), ("groban", -8, (-10, -6))):
    m = lambda k: np.mean(pooled[v][k])
    off = [r["offset"] for r in rp.values() if r["voice"] == v and r["shift"] == s]
    show("5.5 layout", "two renders sounded strained alone at keys whose neighbours were fine, with the pitch correct",
         f"{v} {s:+d}: blind strain {m(s):.0f} against {m(nb[0]):.0f} at {nb[0]:+d} and {m(nb[1]):.0f} at {nb[1]:+d}; "
         f"sung minus intended pitch {off[0]:+.2f} semitones")
allo = [r["offset"] for r in rp.values()]
show("5.5 layout", "(for comparison) sung minus intended pitch over every rated render with a pitch track", f"{len(allo)} clips, {min(allo):+.2f} to {max(allo):+.2f}")
rung = [[s for s, *_ in side[v]["steps"]].index(ref[v]) + 1 for v in V]
show("5.5 layout", "on the ladder the sweet spot sat on the fourth rung for 6 of 8 voices", f"{rung.count(4)} of 8 (rungs {rung})")
lay = {"pilot": {v: pilot[v]["sweet"] for v in V}, "side by side": ref, "blind (strain-50 key)": {v: c for v, c in h1}}
txt, ok = [], True
for nm, rf in lay.items():
    sg = {r: np.mean([rule[v][r] - rf[v] for v in rf]) for r in RULES}; ab = {r: np.mean([abs(rule[v][r] - rf[v]) for v in rf]) for r in RULES}
    hi = max(sg, key=sg.get); ok &= hi in ("median", "clip") and min(ab, key=ab.get) == "topnote"
    txt.append(f"{nm} ({len(rf)} voices): mean signed " + ", ".join(f"{NAME[r]} {sg[r]:+.2f}" for r in RULES) + f"; closest {NAME[min(ab, key=ab.get)]}")
show("5.5 layout", "in every layout Median or Clip was highest and Top note closest", f"holds: {ok}\n       " + "\n       ".join(txt))

# ---------------------------------------------------------------- what LLMs picked
cl = [llm[k] for k in llm if k[0].startswith("claude")]
show("5.5 LLMs", "Claude Haiku, Sonnet and Opus 5.5 missed the reference by 4.2 to 5.7 in every condition, always too high",
     f"{min(a for a, _ in cl)} to {max(a for a, _ in cl)}; too high on average in every condition: {all(s > 0 for _, s in cl)}")
for m, p in (("gemma-4-31b-fp8", "5.4 to 7.4"), ("qwen3.5-27b-fp8", "4.0 to 5.1")):
    x = [llm[k] for k in llm if k[0] == m]
    show("5.5 LLMs", f"{m} missed by {p}, also too high", f"{min(a for a, _ in x)} to {max(a for a, _ in x)}; too high: {all(s > 0 for _, s in x)}")
for m, p in (("gemma-4-e4b-it", "4.7"), ("qwen2.5-omni-7b", "6.6")):
    show("5.5 LLMs", f"{m}, hearing the recording, missed by {p}", f"{listen[m][0]} (signed {listen[m][1]:+.1f})")
e6 = [rule[v]["topnote"] - ref[v] for v in SIX]
show("5.5 LLMs", "Top note missed by 1.3 on the same six", f"{np.mean(np.abs(e6)):.2f}")
sig = defaultdict(dict)
for f in sorted((HERE / "llm/results").glob("*.json")):
    res = json.load(open(f))
    for cond in ("name", "numbers", "anon", "image"):
        sig[res["model"]][cond] = round(float(np.mean([abs(r["shift"] - r["gold"]) for r in res["rows"] if r["cond"] == cond and r["shift"] is not None])), 1)
for grp, ms in (("Claude", [m for m in sig if m.startswith("claude")]), ("the open models", [m for m in sig if not m.startswith("claude")])):
    num = [sig[m][c] for m in ms for c in ("numbers", "anon")]; nm_ = [sig[m]["name"] for m in ms]
    show("5.5 LLMs", "against the composer's earlier sighted keys, the measurement helped: Claude 1.8 to 2.0 against 2.9 to 3.6; "
         "the open models 2.1 to 3.0 against 3.6 to 4.8", f"{grp}: with the numbers {min(num)} to {max(num)}; by name {min(nm_)} to {max(nm_)}")

# ---------------------------------------------------------------- why Top note works
show("5.5 why", "Top note misses: Jackson and Bolton 3 too high; Groban 4 too low",
     ", ".join(f"{v} {rule[v]['topnote'] - ref[v]:+d}" for v in ("jackson", "bolton", "groban")))

# ---------------------------------------------------------------- Figure 3
print("\n[Figure 3] reference key, then each rule's key minus the reference (Top note, Top, Median, Clip)")
for v in V:
    print(f"    {v:9s} {ref[v]:+3d}   " + "  ".join(f"{rule[v][r] - ref[v]:+3d}" for r in RULES))
