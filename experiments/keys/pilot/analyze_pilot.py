#!/usr/bin/env python3
"""analyze_pilot.py: the pilot ladder (ordered, sighted) against the key rules, the composer's earlier keys and the models.

    python3 analyze_pilot.py          # RESULT.md and pilot-joined.json (which blind/make_clips.py reads)

The composer's definitions, given after rating: the sweet spot is the range where the voice does not struggle to hit
the highest note of the excerpt, natural, with a little tension (more of the voice's colour). Too high is screaming or
struggling on the high note. The slider is a strain scale (about 50 = a little tension), not a quality score.
Layout: per voice, six keys low to high, with the Median rule's key always on the 4th rung (-6..+4 around it), so the
answer's position could be learned after a few voices; the blind round is the shuffled redo.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent; K = HERE.parent
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
nn = lambda m: f"{NOTE[int(round(m)) % 12]}{int(round(m)) // 12 - 1}"
PROF = json.load(open(K / "data/profiles.json"))
EAR = {"buble": -8, "jackson": -4, "clarkson": 2, "bolton": -4, "ariana": 2, "wonder": 2}   # the composer's keys by ear on the canvas
TOP_WRITTEN = PROF["songs"]["attya"]["high"]   # the excerpt's (and the song's) highest written note, D5


def pilot():
    key = json.load(open(HERE / "key.json")); out = {}
    for f in sorted((HERE / "answers").glob("*.json")):
        d = json.load(open(f))
        v = key[d["steps"][0]["clip"]]["voice"]
        steps = sorted(({"shift": key[s["clip"]]["shift"], "register": s["register"], "strain": s["score"], "clip": s["clip"]} for s in d["steps"]), key=lambda s: s["shift"])
        out[v] = {"pred": key[d["steps"][0]["clip"]]["pred"], "sweet": key[d["sweet"]]["shift"], "steps": steps, "at": d.get("at")}
    return out


def crossing(steps, level=50):
    """Shift where the strain slider crosses `level` (linear between rungs); None if all rungs are above it (censored)."""
    for a, b in zip(steps, steps[1:]):
        if a["strain"] <= level <= b["strain"] and b["strain"] != a["strain"]:
            return a["shift"] + (level - a["strain"]) / (b["strain"] - a["strain"]) * (b["shift"] - a["shift"])
    return steps[0]["shift"] if steps[0]["strain"] == level else None


def pct(v, q):          # the singer's own q-th percentile note (1-99% trimmed pitch track)
    return PROF["voices"][v]["percentiles_1_to_99"][q - 1]


def main():
    L = pilot(); rows = []; lines = []
    for v, d in L.items():
        vp = PROF["voices"][v]; r = PROF["rules"][f"attya/{v}"]
        right = [s["shift"] for s in d["steps"] if s["register"] == "right"]
        bottom = d["steps"][0]
        top_at_sweet = TOP_WRITTEN + d["sweet"]
        rows.append({"voice": v, "rule_median": r["median"], "rule_top": r["top"], "rule_clip": r.get("clip"), "ear_1nov": EAR.get(v),
                     "sweet": d["sweet"], "right_band": [min(right), max(right)] if right else None,
                     "strain50": crossing(d["steps"]), "sweet_is_bottom": d["sweet"] == bottom["shift"],
                     "floor_closed": bottom["register"] == "low", "top_note_at_sweet": nn(top_at_sweet),
                     "top_pct_in_voice": vp["share_below"][str(top_at_sweet)] * 100, "voice_p90": nn(vp["p90"]), "voice_median": nn(vp["median"]),
                     "whole_recording": vp["source"] == "whole recording", "strain_steps": [s["strain"] for s in d["steps"]],
                     "registers": [s["register"][0] for s in d["steps"]], "shifts": [s["shift"] for s in d["steps"]], "saved_at": d["at"]})
    json.dump(rows, open(HERE / "pilot-joined.json", "w"), indent=1)
    lines += ["# Pilot ladder (ordered layout, the Median rule's key always on rung 4 of 6)", "",
              "| voice | rule (median) | rule (top) | ear, canvas | ladder sweet | 'about right' band | strain 50 at | top note at sweet | = singer's own percentile | sweet on bottom rung |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s50 = "below ladder" if r["strain50"] is None else f"{r['strain50']:+.1f}"
        lines.append(f"| {r['voice']} | {r['rule_median']:+d} | {r['rule_top']:+d} | {'' if r['ear_1nov'] is None else format(r['ear_1nov'], '+d')} | **{r['sweet']:+d}** | "
                     f"{r['right_band'][0]:+d}..{r['right_band'][1]:+d} | {s50} | {r['top_note_at_sweet']} | {r['top_pct_in_voice']:.0f}{'' if r['whole_recording'] else ' (clip only)'} | "
                     f"{'yes' + ('' if r['floor_closed'] else ', floor open') if r['sweet_is_bottom'] else 'no'} |")
    e_med = [r["sweet"] - r["rule_median"] for r in rows]; e_top = [r["sweet"] - r["rule_top"] for r in rows]
    e_ear = [r["sweet"] - r["ear_1nov"] for r in rows if r["ear_1nov"] is not None]
    lines += ["", f"- Sweet minus median rule: {e_med} (mean {np.mean(e_med):+.1f}); minus top rule: {e_top} (mean {np.mean(e_top):+.1f}); "
              f"minus ear on the canvas: {e_ear} (mean {np.mean(e_ear):+.1f}).",
              f"- Sweet spot on the bottom rung for {sum(r['sweet_is_bottom'] for r in rows)}/8 voices; floor closed by a 'too low' rung "
              f"for {sum(r['floor_closed'] for r in rows)}/8. Strain steps per rung: " + "; ".join(f"{r['voice']} {r['strain_steps']}" for r in rows) + "."]
    # leave-one-out top-anchor rule: shift = round(voice percentile q - song top), q chosen on the other voices
    qs = list(range(30, 100, 5)); loo = []
    for i, r in enumerate(rows):
        best = min(qs, key=lambda q: sum(abs(round(pct(o["voice"], q) - TOP_WRITTEN) - o["sweet"]) for j, o in enumerate(rows) if j != i))
        pred = round(pct(r["voice"], best) - TOP_WRITTEN); loo.append((r["voice"], best, pred, pred - r["sweet"]))
    lines += [f"- Top-anchor rule, leave one voice out (song's top note on the singer's own q-th percentile, q fitted on the other 7): "
              + ", ".join(f"{v} q{q} {p:+d} (err {e:+d})" for v, q, p, e in loo) + f"; mean abs error {np.mean([abs(e) for *_, e in loo]):.1f} "
              f"vs median rule {np.mean(np.abs(e_med)):.1f}, top rule {np.mean(np.abs(e_top)):.1f}. (Lower bound where the floor is open.)"]
    # models against the pilot sweet spots, the 6 All the Things You Are cases
    sweet = {f"attya/{r['voice']}": r["sweet"] for r in rows}
    lines += ["", "## Model key picks scored against the pilot (6 All the Things You Are cases; error = answer - pilot sweet spot)", "",
              "| who | condition | mean abs error | mean signed | within ±2 | vs the composer's canvas keys (mean abs) |", "|---|---|---|---|---|---|"]
    for k, rule in (("median", "rule_median"), ("top", "rule_top")):
        e = [r[rule] - r["sweet"] for r in rows if f"attya/{r['voice']}" in sweet and r["voice"] in EAR]
        lines.append(f"| center.py | rule {k} | {np.mean(np.abs(e)):.1f} | {np.mean(e):+.1f} | {sum(abs(x) <= 2 for x in e)}/6 | {np.mean([abs(r[rule] - EAR[r['voice']]) for r in rows if r['voice'] in EAR]):.1f} |")
    for f in sorted((K / "llm/results").glob("*.json")):
        res = json.load(open(f))
        for cond in ("name", "numbers", "anon", "image"):
            rs = [x for x in res["rows"] if x["cond"] == cond and x["case"] in sweet and x["shift"] is not None]
            if rs:
                e = [x["shift"] - sweet[x["case"]] for x in rs]
                lines.append(f"| {res['model']} | {cond} | {np.mean(np.abs(e)):.1f} | {np.mean(e):+.1f} | {sum(abs(x) <= 2 for x in e)}/{len(e)} | {np.mean([abs(x['shift'] - x['gold']) for x in rs]):.1f} |")
    for f in sorted((K / "llm/listen-results").glob("*.json")):
        res = json.load(open(f)); rs = [x for x in res["rows"] if x["q"] == "key" and x["case"] in sweet and x["shift"] is not None]
        if rs:
            e = [x["shift"] - sweet[x["case"]] for x in rs]
            lines.append(f"| {res['model']} | hears the voice | {np.mean(np.abs(e)):.1f} | {np.mean(e):+.1f} | {sum(abs(x) <= 2 for x in e)}/{len(e)} | {np.mean([abs(x['shift'] - x['gold']) for x in rs]):.1f} |")
    (HERE / "RESULT.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    main()
