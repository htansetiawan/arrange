#!/usr/bin/env python3
"""align.py — find the composer's written melody inside the performance (/arrange-lyrics, step 1).

    python align.py --abc-notes reference.json --midi piano.mid --analysis piano-analysis.json
                         --window 73 116 -o jobs/L1/melody.json

The written line (a list of [start_s, end_s, pitch] or plain pitches) is
aligned by dynamic programming to the transcription's right-hand notes inside
the window: equal pitch costs 0, an octave 0.5, anything else 1, a skipped
written note 1, a skipped played note 0.3. Each written note gets the played
note's onset; its end is the next matched onset (or the played note's end).
Positions are then expressed in the measured map's bar:beat. Unmatched
written notes are reported, never invented. (analysis python)
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
import pretty_midi

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
from clock import Clock, ClockError  # noqa: E402  (the one clock lives in /arrange-plan)


def align(written, played):
    n, m = len(written), len(played)
    INF = 1e9
    D = np.full((n + 1, m + 1), INF); D[0, 0] = 0
    B = np.zeros((n + 1, m + 1), dtype=np.int8)
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, arg = INF, 0
            if i > 0 and j > 0:
                d = abs(written[i - 1] - played[j - 1][2])
                c = 0.0 if d == 0 else 0.5 if d % 12 == 0 else 1.0
                if D[i - 1, j - 1] + c < best:
                    best, arg = D[i - 1, j - 1] + c, 1
            if i > 0 and D[i - 1, j] + 1.0 < best:
                best, arg = D[i - 1, j] + 1.0, 2
            if j > 0 and D[i, j - 1] + 0.3 < best:
                best, arg = D[i, j - 1] + 0.3, 3
            D[i, j], B[i, j] = best, arg
    i, j, pairs = n, m, []
    while i > 0 or j > 0:
        if B[i, j] == 1:
            pairs.append((i - 1, j - 1)); i, j = i - 1, j - 1
        elif B[i, j] == 2:
            pairs.append((i - 1, None)); i -= 1
        else:
            j -= 1
    return list(reversed(pairs)), float(D[n, m])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--abc-notes", required=True); ap.add_argument("--midi", required=True); ap.add_argument("--analysis", required=True)
    ap.add_argument("--window", type=float, nargs=2, required=True); ap.add_argument("--lowest", type=int, default=58)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    ref = json.load(open(a.abc_notes))
    written = [int(r[2]) if isinstance(r, (list, tuple)) else int(r) for r in ref]
    pm = pretty_midi.PrettyMIDI(a.midi)
    played = sorted((float(n.start), float(n.end), int(n.pitch)) for i in pm.instruments for n in i.notes
                    if a.window[0] <= n.start <= a.window[1] and n.pitch >= a.lowest)
    # keep the highest note per 40 ms attack cluster: the sung line lives on top
    top, cur = [], []
    for n in played:
        if cur and n[0] - cur[0][0] > 0.04:
            top.append(max(cur, key=lambda x: x[2])); cur = []
        cur.append(n)
    if cur:
        top.append(max(cur, key=lambda x: x[2]))
    pairs, cost = align(written, top)
    clk = Clock(json.load(open(a.analysis)))
    out, unmatched = [], []
    for wi, pj in pairs:
        if pj is None:
            unmatched.append({"index": wi, "pitch": written[wi]}); continue
        st, en, pitch = top[pj]
        out.append({"index": wi, "written_pitch": written[wi], "played_pitch": pitch, "t": round(st, 3), "end": round(en, 3)})
    for x, y in zip(out, out[1:]):
        x["end"] = round(min(x["end"] if x["end"] > x["t"] + 0.08 else y["t"], y["t"]), 3)
    for x in out:
        try:
            bar, beat = clk.at(x["t"]); x["bar"], x["beat"] = bar, round(beat, 3)
        except ClockError:
            x["bar"], x["beat"] = None, None
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({"method": "written line aligned to the transcription's top notes (DP, pitch cost)", "window_s": a.window, "cost": cost,
               "written_notes": len(written), "matched": len(out), "unmatched": unmatched, "octave_differences": sum(1 for x in out if x["written_pitch"] != x["played_pitch"]),
               "notes": out}, open(a.out, "w"), indent=1)
    print(f"{len(out)}/{len(written)} written notes found in the performance ({len(unmatched)} unmatched, {sum(1 for x in out if x['written_pitch'] != x['played_pitch'])} at a different octave); "
          f"first {out[0]['t']}s (bar {out[0]['bar']}:{out[0]['beat']}), last {out[-1]['t']}s (bar {out[-1]['bar']}:{out[-1]['beat']}); alignment cost {cost:.1f}")
    if unmatched:
        print("UNMATCHED written notes (index, pitch):", [(u["index"], u["pitch"]) for u in unmatched])


if __name__ == "__main__":
    main()
