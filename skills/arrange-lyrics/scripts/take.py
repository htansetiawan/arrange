#!/usr/bin/env python3
"""take.py — a played take and the composer's taps into the tempo map and the fit (/arrange-lyrics; plain python).

    python take.py --take take.json --grid grid.json --analysis piano-analysis.json --lines lines.txt --out-analysis piano-analysis.tapped.json -o jobs/verse1/

1. Tempo map from the taps: the composer's beats are half beats of the slow
   map, so every other tap is a map beat; beats before the first tap and after
   the last keep the measured spacing. Method "creator-tapped".
2. The take: the composer's lead against their own taps is measured (median of onset minus
   nearest tap) and removed; onsets snap to quarters of the composer's beat; a note lasts
   until the next onset in its phrase (keys are tapped, not held); phrases
   split at gaps of 1.5 beats or more.
3. Words: line k goes on phrase k; one syllable per note; a line one
   syllable longer than its phrase gets its first note split in two at the
   same pitch (as in "Foot-steps"); notes beyond the words are kept,
   unsung, for the composer to fill.
"""
import argparse, copy, json, re, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
from lay import syllabify_text  # noqa: E402
from feel import feel, subdivision  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--take", required=True); ap.add_argument("--grid", required=True); ap.add_argument("--analysis", required=True)
    ap.add_argument("--lines", required=True); ap.add_argument("--out-analysis", required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--from-t", type=float, default=0.0, help="use only the take's notes from this time on")
    ap.add_argument("--first-tap-beat", type=int, help="the composer's beat number of the first tap, counted from 0 at bar 1 beat 1 (default: bar 2 beat 1)")
    a = ap.parse_args()
    take = json.load(open(a.take)); take = take.get("data", take)
    grid = json.load(open(a.grid)); grid = grid.get("data", grid)
    taps = [t for i, t in enumerate(grid["taps"]) if i == 0 or t - grid["taps"][i - 1] > 0.3]
    an = json.load(open(a.analysis)); meas = Clock(an)
    per, bpb, _ts = feel(an); a.bpb = bpb; a.sub = subdivision(_ts)
    if a.first_tap_beat is None: a.first_tap_beat = bpb
    if len(taps) < 2:   # no tapped beats: the measured map is the grid, as the page showed it
        Path(a.out_analysis).write_text(json.dumps(an, indent=1))
        bt = [b["t"] for b in meas.beats]; hb = {}
        for o, t in enumerate(bt):   # the composer's beats: each map beat and its even subdivisions up to the next
            for j in range(per):
                if j == 0 or o + 1 < len(bt):
                    hb[per * o + j] = t + ((bt[o + 1] - t) * j / per if j else 0)
        return place(a, take, an, Clock(an), ["no beats tapped: the measured beat grid is used as is"], (bt[1] - bt[0]) / per, hb)
    report = [f"{len(taps)} taps used ({len(grid['taps']) - len(taps)} dropped as double taps), {taps[0]:.2f}–{taps[-1]:.2f} s, median beat {statistics.median([b - a for a, b in zip(taps, taps[1:])]):.3f} s"]
    # 1. tempo map: the composer's beat k (0 = bar 1 beat 1) at taps[k - first]; map beats are the composer's even beats
    first = a.first_tap_beat
    hb = {first + i: t for i, t in enumerate(taps)}
    step0 = taps[1] - taps[0]
    k = first - 1
    while k >= 0:
        hb[k] = hb[k + 1] - step0; k -= 1
    if hb[0] < 0:
        report.append(f"note: by your first tap, bar 1 would start at {hb[0]:.2f} s, before the recording; kept as is")
    last_k = first + len(taps) - 1
    # after the taps: continue with the measured map's spacing from the matching point
    t_last = taps[-1]; mb, mbt = meas.at(t_last); o_last = meas._ordinal(mb, mbt)
    kk = last_k; o = o_last
    while True:
        o += 1.0 / per; kk += 1
        try:
            bar, beat = meas._position(o); t = meas.t(bar, beat)[0]
        except Exception:
            break
        hb[kk] = t
    beats = []
    for k in sorted(hb):
        if k % per == 0:
            mo = k // per   # map ordinal
            beats.append({"t": round(hb[k], 4), "bar": mo // meas.bpb + 1, "beat": mo % meas.bpb + 1})
    tapped = copy.deepcopy(an); tm = tapped["tempo_map"]
    tm["beats"] = beats; tm["method"] = f"creator-tapped ({per} of the composer's beats per map beat; measured spacing outside the taps)"; tm["inspection"] = "creator-tapped"
    tm["revision"] = int(tm.get("revision", 0)) + 1; tm["unresolved"] = []
    tm.setdefault("corrections", []).append({"source": "creator taps", "taps": len(taps), "span_s": [round(taps[0], 3), round(taps[-1], 3)]})
    Path(a.out_analysis).write_text(json.dumps(tapped, indent=1))
    clk = Clock(tapped)
    return place(a, take, tapped, clk, report, step0, hb)


def place(a, take, an_used, clk, report, step0, hb):
    """The take on the grid: lead removed, notes snapped, phrases, words laid."""
    # 2. the take
    notes = sorted([n for n in take["notes"] if n["t"] >= a.from_t], key=lambda n: n["t"])
    # the same pitch struck twice within 120 ms is one note recorded twice (a page loaded twice), not two notes
    dedup = []
    for n in notes:
        if dedup and any(d["pitch"] == n["pitch"] and abs(d["t"] - n["t"]) < 0.12 for d in dedup[-3:]):
            continue
        dedup.append(n)
    # two different keys within 80 ms are a fumble: both are kept, but say so, because snapping will put them on one spot
    for x, y in zip(dedup, dedup[1:]):
        if y["pitch"] != x["pitch"] and y["t"] - x["t"] < 0.08:
            report.append(f"fumble at {x['t']:.2f} s: {NAMES[x['pitch'] % 12]}{x['pitch'] // 12 - 1} and {NAMES[y['pitch'] % 12]}{y['pitch'] // 12 - 1} {1000 * (y['t'] - x['t']):.0f} ms apart will land on the same beat; play that spot again")
    if len(dedup) < len(notes):
        report.append(f"{len(notes) - len(dedup)} notes were recorded twice within 120 ms and merged ({len(dedup)} notes kept)")
    notes = dedup
    tap_list = sorted(hb.items())
    def nearest_beat(t):
        return min(tap_list, key=lambda kt: abs(kt[1] - t))
    lead = statistics.median([n["t"] - nearest_beat(n["t"])[1] for n in notes])
    report.append(f"you play {abs(lead) * 1000:.0f} ms {'ahead of' if lead < 0 else 'behind'} your own taps (median over {len(notes)} notes); removed before snapping")
    def his_beat(t):   # fractional composer's beat at time t
        ks = [k for k, tt in tap_list if tt <= t]
        k = ks[-1] if ks else tap_list[0][0]
        t0 = hb[k]; t1 = hb.get(k + 1, t0 + step0)
        return k + (t - t0) / (t1 - t0)
    def t_of(b):
        k = int(b // 1); frac = b - k
        t0 = hb.get(k); t1 = hb.get(k + 1, (t0 or 0) + step0)
        return t0 + frac * (t1 - t0)
    pos = [round(his_beat(n["t"] - lead) * a.sub) / a.sub for n in notes]
    phrases, cur = [], [0]
    for i in range(1, len(notes)):
        if pos[i] - pos[i - 1] >= 2.5:   # a phrase ends where the next onset is 2.5 or more of the composer's beats away
            phrases.append(cur); cur = []
        cur.append(i)
    phrases.append(cur)
    lines = [ln.strip() for ln in Path(a.lines).read_text().splitlines() if ln.strip()]
    rows = []
    for pi, ph in enumerate(phrases):
        seq = []
        for j, i in enumerate(ph):
            on = pos[i]
            if j + 1 < len(ph):
                off = pos[ph[j + 1]]
            else:
                off = on + max(1.0, round((notes[i]["end"] - notes[i]["t"]) / step0 * a.sub) / a.sub)
            seq.append({"pitch": notes[i]["pitch"], "on": on, "off": off})
        words = lines[pi] if pi < len(lines) else ""
        syl = [(s, w) for w in re.findall(r"[A-Za-z']+", words) for s in syllabify_text(w)]
        if len(syl) >= len(seq) + 1:
            n0 = seq[0]; mid = n0["on"] + (n0["off"] - n0["on"]) / 2; second = dict(n0); second["on"] = mid; n0["off"] = mid; seq.insert(1, second)
            report.append(f"phrase {pi + 1}: a syllable more than notes; your first note is split in two at the same pitch")
        if len(syl) >= len(seq) + 1:
            nl = seq[-1]; cut = nl["on"] + (1.0 if nl["off"] - nl["on"] >= 2.0 else (nl["off"] - nl["on"]) / 2)
            last = dict(nl); last["on"] = cut; nl["off"] = cut; seq.append(last)
            report.append(f"phrase {pi + 1}: still a syllable more; your last note is split too, a short note then the held one ('{' '.join(x[0] for x in syl[-2:])}')")
        if len(syl) > len(seq):
            left = " ".join(x[0] for x in syl[len(seq):])
            report.append(f"phrase {pi + 1}: WARNING {len(syl) - len(seq)} syllable(s) have no note and are NOT sung: '{left}'; play more notes or shorten the line")
            print(f"WARNING: phrase {pi + 1}: words without notes: {left}", file=sys.stderr)
        for j, n in enumerate(seq):
            s, w = syl[j] if j < len(syl) else ("", None)
            b0 = int(n["on"] // 1); 
            rows.append({"t": round(t_of(n["on"]), 3), "end": round(t_of(n["off"]), 3), "pitch": n["pitch"], "bar": b0 // a.bpb + 1, "beat": b0 % a.bpb + 1 + (n["on"] - b0),
                         "text": s, "kind": "note" if s else "unsung", "word": w, "placed": "played by the composer"})
        report.append(f"phrase {pi + 1}: {len(seq)} notes from {t_of(seq[0]['on']):.1f} s (bar {int(seq[0]['on'] // a.bpb) + 1} beat {seq[0]['on'] % a.bpb + 1:g}): " + " ".join(NAMES[n['pitch'] % 12] + str(n['pitch'] // 12 - 1) for n in seq)
                      + (f" ← '{words}' ({len(syl)} syllables)" if words else " ← no words yet") + (f"; {len(seq) - len(syl)} note(s) without words" if len(seq) > len(syl) else ""))
    for k, r in enumerate(rows):
        r["index"] = k
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump({"take": a.take, "lines": lines, "rows": rows, "report": report}, open(out / "score-with-unsung.json", "w"), indent=1, ensure_ascii=False)
    for r in report:
        print("TAKE:", r)


if __name__ == "__main__":
    main()
