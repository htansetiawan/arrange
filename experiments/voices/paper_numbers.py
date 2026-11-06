#!/usr/bin/env python3
"""paper_numbers.py: every number in Sections 5.3 and 5.4 of the paper, from the stored ratings, measures and voice
check in this folder. No model, no audio, no network. Needs numpy and scipy.

    python3 paper_numbers.py

Each line gives the paper's claim, then the value computed here.
"""
import csv, json
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
AUTHOR = {"henry", "mine", "own-score", "own-seedvc", "henry-yard"}     # voice ids of the author's own voice


def show(section, claim, value):
    print(f"[{section}] {claim}\n    -> {value}")


def joined(page):
    """One row per rated clip: the hidden key joined with the composer's answer."""
    key = json.load(open(HERE / page / "key.json")); rows = []
    for f in sorted((HERE / page / "answers").glob("*.json")):
        a = json.load(open(f)); k = key[a["clip"]]
        rows.append({"clip": a["clip"], "song": k["song"], "voice": k["voice"], "repeat": k["repeat"], "system": k.get("system"),
                     "shift": k.get("shift"), "score": a["score"], "tags": a["tags"]})
    assert len(rows) == len(key), "a clip has no answer"
    return rows


# ---------------------------------------------------------------- 5.3 pitch
vc = json.load(open(HERE / "voice-check/voice-check.json"))["renders"]
meas = list(csv.DictReader(open(HERE / "measures/measures.csv")))
cp = [r for r in meas if r["song"] == "color-purple" and not r["repeat_of"] and (r["voice"] in AUTHOR or r["voice"] in ("groban", "pavarotti"))]
share = [r["in_tune_50c"] for r in vc] + [float(r["pitch_within50"]) for r in cp]
cents = [r["median_cents_off"] for r in vc] + [float(r["pitch_err_cents"]) for r in cp]
show("5.3", "in the four voices we measured (the author, Groban, Ingram, Pavarotti), every route kept the notes in tune: "
     "97 to 100% of notes within a quarter tone of the score, typically 10 cents off",
     f"voice check, {len(vc)} renders (targets {sorted({r['singer'] for r in vc})}, plus the Groban-sung source): "
     f"{min(r['in_tune_50c'] for r in vc):.0%} to {max(r['in_tune_50c'] for r in vc):.0%} within 50 cents, median cents off "
     f"{min(r['median_cents_off'] for r in vc)} to {max(r['median_cents_off'] for r in vc)}\n"
     f"       Color Purple rating stems ({', '.join(r['voice'] for r in cp)}): within 50 cents "
     f"{', '.join(f'{float(r['pitch_within50']):.0%}' for r in cp)}, median cents off {', '.join(f'{float(r['pitch_err_cents']):.1f}' for r in cp)}\n"
     f"       all {len(share)}: {min(share):.0%} to {max(share):.0%}; median of the medians {np.median(cents):.1f} cents")

# ---------------------------------------------------------------- 5.3 which singer, by ear
d = joined("systems"); first = [r for r in d if not r["repeat"]]
mean = {s: np.mean([r["score"] for r in first if r["system"] == s]) for s in ("SoulX", "Seed-VC", "TechSinger")}
n = {s: sum(r["system"] == s for r in first) for s in mean}
show("5.3", "a blind test of 35 clips", f"{len(d)} clips ({n['SoulX']} SoulX, {n['Seed-VC']} Seed-VC, {n['TechSinger']} TechSinger, "
     f"{sum(r['repeat'] for r in d)} hidden repeats)")
show("5.3", "SoulX-Singer 95.9 of 100 on average, Seed-VC 88.5 on the same songs, singers and keys",
     f"SoulX {mean['SoulX']:.1f}, Seed-VC {mean['Seed-VC']:.1f} (first hearings only)")
pair = lambda r: (r["song"], r["voice"], r["shift"])
sx = {pair(r): r["score"] for r in first if r["system"] == "SoulX"}; sv = {pair(r): r["score"] for r in first if r["system"] == "Seed-VC"}
diff = np.array([sx[k] - sv[k] for k in sorted(set(sx) & set(sv))], float)
boot = np.random.default_rng(0).choice(diff, (10000, len(diff)), replace=True).mean(1)
lo, hi = np.percentile(boot, [2.5, 97.5])
w = stats.wilcoxon(diff)
show("5.3", "SoulX higher by 7.4 (95% bootstrap CI 1.9 to 13.3), better on 8 of 10 pairs (Wilcoxon p = 0.049)",
     f"+{diff.mean():.1f} (percentile bootstrap, 10,000 resamples of the {len(diff)} paired differences, numpy default_rng(0): "
     f"{lo:.1f} to {hi:.1f}); better on {(diff > 0).sum()}, worse on {(diff < 0).sum()} of {len(diff)}; Wilcoxon signed-rank p = {w.pvalue:.3f}")
ts = [r for r in d if r["system"] == "TechSinger"]
show("5.3", "TechSinger's built-in singers scored 22.8, every clip tagged as glitching",
     f"{mean['TechSinger']:.1f} (n = {n['TechSinger']}); tagged Glitch {sum('Glitch' in r['tags'] for r in ts if not r['repeat'])} of "
     f"{n['TechSinger']} ({sum('Glitch' in r['tags'] for r in ts)} of {len(ts)} with the repeat)")
rep = [abs(r["score"] - next(f["score"] for f in first if f["system"] == r["system"] and pair(f) == pair(r))) for r in d if r["repeat"]]
show("5.3", "hidden repeats came back within 4 points on average", f"|difference| {rep}, mean {np.mean(rep):.1f}")

# ---------------------------------------------------------------- 5.4 fine-tuning
ft = json.load(open(HERE / "finetune/finetune-clips.json")); sec = sum(r["seconds"] for r in ft)
show("5.4", "fine-tuned the converter on 8.6 minutes of the author's own singing, cut into 113 clips",
     f"{len(ft)} clips, {sec:.1f} s = {sec / 60:.1f} minutes")
g = {r["name"]: r for r in vc if r["singer"] == "henry"}
a, b = g["Seed-VC zero-shot"], g["Seed-VC fine-tuned on the author"]
show("5.4", "speaker-verification similarity against his reference clip rose from 0.88 to 0.92",
     f"{a['like_ref']:.3f} -> {b['like_ref']:.3f} (against a held-out stretch of the same recording: {a['like_heldout']:.3f} -> {b['like_heldout']:.3f})")

# ---------------------------------------------------------------- 5.4 eight measures against the ear
d = joined("ratings")
ear = {}
for r in d: ear.setdefault((r["song"], r["voice"]), []).append(r["score"])
ear = {k: float(np.mean(v)) for k, v in ear.items()}           # hidden repeats averaged with their first hearing
items = {}
for r in meas: items.setdefault((r["song"], r["voice"]), r)
good = [k for k in items if not k[1].startswith("ts-")]        # without TechSinger's built-in singers
show("5.4", "34 blind-rated clips (song x voice)", f"{len(d)} clips rated, {sum(r['repeat'] for r in d)} of them hidden repeats: "
     f"{len(items)} song x voice items")
show("5.4", "the 31 clips he rated 72 to 100", f"{len(good)} items without TechSinger; ear {min(ear[k] for k in good):.1f} to {max(ear[k] for k in good):.1f}")
EIGHT = [("naturalness predictor (SingMOS-Pro)", "singmos_pro"), ("energy of the singer's ring (SPR)", "spr_db"),
         ("pitch movement within notes", "steady_cents"), ("vibrato rate", "vib_rate_hz"), ("vibrato extent", "vib_extent_cents"),
         ("share of notes with vibrato", "vib_frac"), ("pitch error against the score", "pitch_err_cents"),
         ("harmonics-to-noise ratio", "hnr_db"), ("word error (Whisper)", "wer"), ("character error (Whisper)", "cer"),
         ("speaker similarity", "likeness")]
OTHER = [("SPR as band energy", "spr_energy_db"), ("HNR, median", "hnr_median_db"), ("share of notes within 50 cents", "pitch_within50"),
         ("voiced share", "voiced_frac")]
res = []
for name, col in EIGHT + OTHER:
    xs = [(float(items[k][col]), ear[k]) for k in good if items[k][col] not in ("", None)]
    r = stats.spearmanr(*zip(*xs)); res.append((name, col, r.statistic, r.pvalue, len(xs)))
top = max(res[:len(EIGHT)], key=lambda x: abs(x[2]))
show("5.4", "no rank correlation exceeded 0.31 in size and none was significant",
     f"largest |rho| {abs(top[2]):.3f} ({top[0]}, p = {top[3]:.2f}); smallest p {min(x[3] for x in res[:len(EIGHT)]):.2f}\n       "
     + "\n       ".join(f"{name:38s} rho {rho:+.2f}  p {p:.2f}  n {k}" + ("   (extra column)" if col in dict(OTHER).values() else "")
                       for name, col, rho, p, k in res))
