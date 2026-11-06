#!/usr/bin/env python3
"""make_clips.py (side-by-side ladder): the composer asked to compare keys side by side, knowing which is lower.
Per voice: the lowest 8 rendered keys (Groban 7), low to high, two semitones apart; voices shown as Voice 1-8 in random
order. Unlike the pilot, the keys are not centred on any rule, and the number of keys and where the blind sweet spot
falls differ by voice.

    ARRANGE_RUNS=/path/to/runs python3 make_clips.py     # ../build/side-by-side/clips/, key.json, ladders.json
"""
import json, os, random, re, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs")) / "all-the-things-cohen"
OUT = HERE.parent / "build/side-by-side"; MP3 = "mp3"
START, LEN = 48.8, 15.0
rng = random.Random(4112027)
used = set()
for p in ("pilot", "blind", "recheck"):
    used |= set(json.load(open(HERE.parent / p / "key.json")))
codes = iter(c for c in rng.sample([f"{a}{b}{c}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in "aeiou" for c in range(10)], 600) if c not in used)
voices = ["groban", "adams", "clarkson", "ariana", "jackson", "bolton", "wonder", "buble"]; rng.shuffle(voices)
(OUT / "clips").mkdir(parents=True, exist_ok=True); key, data = {}, []
for n, v in enumerate(voices, 1):
    shifts = sorted(int(m.group(1)) for f in (RUN / "build/sweep/voice").glob(f"{v}*.{MP3}") if (m := re.fullmatch(rf"{v}([+-]\d+)\.{MP3}", f.name)))[:8]
    steps = []
    for s in shifts:
        c = next(codes)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-t", str(LEN), "-i", str(RUN / f"build/sweep/voice/{v}{s:+d}.{MP3}"), "-af",
                        f"loudnorm=I=-18:TP=-1.5,afade=t=in:d=0.1,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "128k", str(OUT / "clips" / f"{c}.{MP3}")], check=True)
        key[c] = {"voice": v, "shift": s}; steps.append(c)
    data.append({"id": f"v{n}", "label": f"Voice {n}", "steps": steps})
    print(v, shifts)
json.dump(key, open(OUT / "key.json", "w"), indent=1)      # compare with the stored side-by-side/key.json
json.dump(data, open(OUT / "ladders.json", "w"), indent=1)
