#!/usr/bin/env python3
"""render_pitch.py: is each rated render sung at its intended key? Writes data/render-pitch.json.

    python3 render_pitch.py --f0 build/f0/pilot build/f0/blind

Inputs (not distributed): the pitch track of every clip the composer heard in the pilot and the blind round
(`<code>.npy`, Hz, 50 frames a second, 0 = unvoiced, written by measure_clips.py) and the fitted score of
All the Things You Are (`$ARRANGE_RUNS/all-the-things-cohen/plan/fit/fit.json`). For each clip: the median sung note
minus the intended shift minus the median written note of the bars heard (48.8 to 63.8 s). Near 0 means the render
is at its key; the output holds only this offset per clip.
"""
import argparse, json, os
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[1] / "runs"))
START, END = 48.8, 63.8


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--f0", nargs="+", required=True, help="folders of <code>.npy pitch tracks")
    a = ap.parse_args()
    rows = [r for r in json.load(open(RUNS / "all-the-things-cohen/plan/fit/fit.json"))["rows"] if r.get("kind") == "note"]
    seg = [r for r in rows if r["end"] > START and r["t"] < END]
    written = float(np.median(np.repeat([r["pitch"] for r in seg], [max(1, int(round((min(r["end"], END) - max(r["t"], START)) * 50))) for r in seg])))
    keys = {**json.load(open(HERE / "pilot/key.json")), **json.load(open(HERE / "blind/key.json"))}
    out = []
    for d in a.f0:
        for p in sorted(Path(d).glob("*.npy")):
            k = keys[p.stem]; f0 = np.load(p); m = 69 + 12 * np.log2(f0[f0 > 0] / 440)
            out.append({"clip": p.stem, "voice": k["voice"], "shift": k["shift"], "offset": round(float(np.median(m) - written - k["shift"]), 3)})
    (HERE / "data/render-pitch.json").write_text(json.dumps(out, indent=1) + "\n")
    print(len(out), "clips; offset", min(r["offset"] for r in out), "to", max(r["offset"] for r in out))


if __name__ == "__main__":
    main()
