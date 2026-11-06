#!/usr/bin/env python3
"""make_clips.py (recheck): a short blind recheck of the blind round's anomalies, asked for by the composer.
Groban (all 6 keys; strain against key Spearman +0.14), Clarkson -6/-4/-2 (-4 'too high' between two 'too low'),
Jackson -5 (its repeat flipped low to right), plus the lowest keys of Adams, Bolton, Bublé -10 and Ariana -4.
Same clips and settings, new codes, shuffled, no singer twice in a row.

    ARRANGE_RUNS=/path/to/runs python3 make_clips.py     # ../build/recheck/clips/, key.json, order.json
"""
import json, os, random, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs")) / "all-the-things-cohen"
OUT = HERE.parent / "build/recheck"; MP3 = "mp3"
START, LEN = 48.8, 15.0
items = [("groban", s) for s in (-14, -12, -10, -8, -6, -4)] + [("clarkson", s) for s in (-6, -4, -2)] + \
        [("jackson", -5), ("adams", -8), ("bolton", -9), ("buble", -10), ("ariana", -4)]
rng = random.Random(4112026)
used = set(json.load(open(HERE.parent / "pilot/key.json"))) | set(json.load(open(HERE.parent / "blind/key.json")))
codes = iter(c for c in rng.sample([f"{a}{b}{c}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in "aeiou" for c in range(10)], 400) if c not in used)
for _ in range(100000):
    order = items[:]; rng.shuffle(order)
    if all(a[0] != b[0] for a, b in zip(order, order[1:])):
        break
(OUT / "clips").mkdir(parents=True, exist_ok=True); key, data = {}, []
for pos, (v, s) in enumerate(order, 1):
    c = next(codes)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-t", str(LEN), "-i", str(RUN / f"build/sweep/voice/{v}{s:+d}.{MP3}"), "-af",
                    f"loudnorm=I=-18:TP=-1.5,afade=t=in:d=0.1,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "128k", str(OUT / "clips" / f"{c}.{MP3}")], check=True)
    key[c] = {"pos": pos, "voice": v, "shift": s, "repeat": False}; data.append(c)
json.dump(key, open(OUT / "key.json", "w"), indent=1)      # compare with the stored recheck/key.json
json.dump(data, open(OUT / "order.json", "w"))
print(" ".join(f"{key[c]['voice'][:3]}{key[c]['shift']:+d}" for c in data))
