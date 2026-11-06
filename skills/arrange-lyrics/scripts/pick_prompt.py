#!/usr/bin/env python3
"""pick_prompt.py — rank the candidate reference clips in a separated singing recording (/arrange-lyrics; analysis python).

    python pick_prompt.py voices/myvoice --target-median 69 [--top 3] [--write]

A zero-shot singer copies whatever is in its reference clip, so the clip matters
as much as the singer. SoulX's preprocessing (pre/metadata.json, pre/vocal.wav,
pre/acc.wav) gives sung segments; every stretch of 8 to 15 s that starts and ends
at a breath is scored on:
  bleed   how loud the band is under the voice in that stretch (acc vs vocal, dB; lower is cleaner)
  sung    share of the stretch that is sung notes rather than silence
  range   how far the stretch's median note is from the line it will sing (semitones)
  steady  share of sung time on notes held 0.4 s or longer (sustained singing, not speech-like runs)
With --write the best clip becomes prompt.json (prompt.wav -> pre/vocal.wav), and
the runners-up prompt-2.json, prompt-3.json.
"""
import argparse, json
from pathlib import Path

import numpy as np
import soundfile as sf


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("voice_dir"); ap.add_argument("--target-median", type=float, required=True, help="median MIDI pitch the clip will sing (after the shift)")
    ap.add_argument("--top", type=int, default=3); ap.add_argument("--write", action="store_true")
    ap.add_argument("--min-s", type=float, default=8.0); ap.add_argument("--max-s", type=float, default=15.0)
    a = ap.parse_args()
    vd = Path(a.voice_dir); pre = vd / "pre"
    meta = json.load(open(pre / "metadata.json"))
    voc, sr = sf.read(pre / "vocal.wav", dtype="float32", always_2d=True); voc = voc.mean(1)
    acc, sr2 = sf.read(pre / "acc.wav", dtype="float32", always_2d=True); acc = acc.mean(1)
    assert sr == sr2
    cands = []
    for si, s in enumerate(meta):
        txt = s["text"].split(); du = [float(x) for x in s["duration"].split()]; pit = [int(x) for x in s["note_pitch"].split()]
        starts = [0] + [k + 1 for k, t in enumerate(txt) if t == "<SP>" and k + 1 < len(txt)]
        cum = np.concatenate([[0], np.cumsum(du)])
        for b in starts:
            for e in range(b + 1, len(txt) + 1):
                if txt[e - 1] != "<SP>" and e != len(txt):
                    continue
                dur = cum[e] - cum[b]
                if dur < a.min_s or dur > a.max_s:
                    continue
                t0 = s["time"][0] / 1000 + cum[b]; t1 = t0 + dur
                i0, i1 = int(t0 * sr), int(t1 * sr)
                bleed = 20 * np.log10(rms(acc[i0:i1]) / rms(voc[i0:i1]))
                sung = sum(d for d, p in zip(du[b:e], pit[b:e]) if p > 0) / dur
                notes = [p for p in pit[b:e] if p > 0]
                if len(notes) < 6:
                    continue
                rng = abs(float(np.median(notes)) - a.target_median)
                steady = sum(d for d, p in zip(du[b:e], pit[b:e]) if p > 0 and d >= 0.4) / max(1e-9, sum(d for d, p in zip(du[b:e], pit[b:e]) if p > 0))
                score = 2.0 * sung + 1.0 * steady - 0.08 * max(0.0, bleed + 12) - 0.12 * rng
                cands.append(dict(score=round(score, 3), seg=si, b=b, e=e, t=[round(t0, 2), round(t1, 2)], dur=round(dur, 1), bleed_db=round(bleed, 1),
                                  sung=round(sung, 2), steady=round(steady, 2), median=float(np.median(notes)), range_off=round(rng, 1),
                                  text=" ".join(txt[b:e]).replace("<SP>", "/")))
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:   # distinct clips: no two that overlap in time
        if all(c["t"][1] <= p["t"][0] or c["t"][0] >= p["t"][1] for p in picked):
            picked.append(c)
        if len(picked) == a.top:
            break
    for k, c in enumerate(picked, 1):
        print(f"{k}. score {c['score']}  {c['t'][0]:.1f}-{c['t'][1]:.1f} s ({c['dur']} s)  band {c['bleed_db']} dB  sung {c['sung']}  steady {c['steady']}  median {c['median']:.0f} (off {c['range_off']})  | {c['text'][:110]}")
        if a.write:
            s = meta[c["seg"]]; f = lambda key: " ".join(s[key].split()[c["b"]:c["e"]])
            out = dict(index=f"{vd.name}_prompt{k}", language=s["language"], time=[int(c["t"][0] * 1000), int(c["t"][1] * 1000)],
                       duration=f("duration"), text=f("text"), phoneme=f("phoneme"), note_pitch=f("note_pitch"), note_type=f("note_type"))
            json.dump([out], open(vd / ("prompt.json" if k == 1 else f"prompt-{k}.json"), "w"), indent=1, ensure_ascii=False)
    json.dump(picked, open(vd / "prompt-candidates.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
