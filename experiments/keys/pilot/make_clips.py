#!/usr/bin/env python3
"""make_clips.py (pilot ladder): for each voice, the same 15 s of All the Things You Are sung at 6 keys, voice only,
ordered low to high, so the composer finds the sweet spot. Which rung is the Median rule's key is hidden.

    ARRANGE_RUNS=/path/to/runs python3 make_clips.py     # ../build/pilot/clips/, key.json, ladders.json (the page's data)

Needs the key sweep renders ($ARRANGE_RUNS/all-the-things-cohen/build/sweep/voice/<voice><shift>, MP3, sung by
SoulX-Singer) and the sweep plan (sweep-plan.json: each voice's six shifts and the Median rule's key), plus ffmpeg.
The rating page itself (a claude.ai artifact that played the clips) is not distributed.
"""
import json, os, random, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs")) / "all-the-things-cohen"
OUT = HERE.parent / "build/pilot"; MP3 = "mp3"
START, LEN = 48.8, 15.0          # source time; the sweep stems are on the source clock
plan = json.load(open(RUN / "sweep-plan.json"))
rng = random.Random(4112026)
voices = list(plan); rng.shuffle(voices)
codes = iter(rng.sample([f"{a}{b}{c}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in "aeiou" for c in range(10)], 200))
(OUT / "clips").mkdir(parents=True, exist_ok=True)
key, data = {}, []
for n, v in enumerate(voices, 1):
    steps = []
    for s in sorted(plan[v]["shifts"]):
        stem = RUN / f"build/sweep/voice/{v}{s:+d}.{MP3}"
        if not stem.exists():
            print("missing", stem); continue
        c = next(codes)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-t", str(LEN), "-i", str(stem), "-af",
                        f"loudnorm=I=-18:TP=-1.5,afade=t=in:d=0.1,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "128k",
                        str(OUT / "clips" / f"{c}.{MP3}")], check=True)
        key[c] = {"voice": v, "shift": s, "pred": plan[v]["pred"], "offset_from_pred": s - plan[v]["pred"]}
        steps.append(c)
    data.append({"id": f"v{n}", "label": f"Voice {n}", "steps": steps})
json.dump(key, open(OUT / "key.json", "w"), indent=1)       # compare with the stored pilot/key.json
json.dump(data, open(OUT / "ladders.json", "w"), indent=1)
print(len(key), "clips in", len(data), "ladders")
