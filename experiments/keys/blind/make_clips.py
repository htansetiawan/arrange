#!/usr/bin/env python3
"""make_clips.py (blind round): the pilot's keys again, one clip at a time, shuffled. Same 15 s excerpt and render
settings as the pilot; every voice's pilot keys minus its top rung (clearly too high there) plus 1-2 lower keys where
the pilot's floor was open (and Groban -14, the Top note prediction). Singers and keys interleaved at random, never the
same singer twice in a row; 6 hidden repeats, each at least 20 clips after its first showing. Nothing on the page said
the singer, the key or the rule.

    ARRANGE_RUNS=/path/to/runs python3 make_clips.py     # ../build/blind/clips/, key.json, order.json

Needs ../pilot/pilot-joined.json (from analyze_pilot.py), the stored ../pilot/key.json (codes already used), the key
sweep renders and ffmpeg.
"""
import json, os, random, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs")) / "all-the-things-cohen"
OUT = HERE.parent / "build/blind"; MP3 = "mp3"
START, LEN = 48.8, 15.0
L1 = {r["voice"]: r for r in json.load(open(HERE.parent / "pilot/pilot-joined.json"))}
EXTRA = {"groban": [-14], "adams": [-8], "clarkson": [-6, -4], "ariana": [-6, -4], "jackson": [-11, -9], "bolton": [-9, -7],
         "wonder": [-8, -6], "buble": [-16, -14]}
rng = random.Random(3112026)
used = set(json.load(open(HERE.parent / "pilot/key.json")))
codes = iter(c for c in rng.sample([f"{a}{b}{c}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in "aeiou" for c in range(10)], 400) if c not in used)

items = []   # (voice, shift)
for v, r in L1.items():
    shifts = sorted(set(r["shifts"][:-1]) | set(EXTRA[v]))
    items += [(v, s) for s in shifts]
# repeats: the first key above each voice's pilot sweet spot (where the judgement flips), 6 voices
rep_voices = rng.sample(sorted(L1), 6)
repeats = [(v, L1[v]["sweet"] + 2) for v in rep_voices]
assert all(x in items for x in repeats), repeats


def place_repeats(order):   # insert each repeat >= 20 after its first showing, not next to the same singer
    order = order[:]
    for v, s in repeats:
        i = order.index((v, s))
        ok = [j for j in range(i + 21, len(order) + 1) if order[j - 1][0] != v and (j == len(order) or order[j][0] != v)]
        if not ok:
            return None
        order.insert(rng.choice(ok), (v, s))
    return order


for _ in range(20000):   # shuffle until no singer repeats back to back and every repeat fits
    order = items[:]; rng.shuffle(order)
    if all(a[0] != b[0] for a, b in zip(order, order[1:])) and (order := place_repeats(order)):
        break
else:
    raise SystemExit("no order found")

(OUT / "clips").mkdir(parents=True, exist_ok=True)
key, data, first = {}, [], set()
for pos, (v, s) in enumerate(order, 1):
    c = next(codes); stem = RUN / f"build/sweep/voice/{v}{s:+d}.{MP3}"
    if not stem.exists():
        raise SystemExit(f"missing render {stem}")
    out = OUT / "clips" / f"{c}.{MP3}"
    if not out.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-t", str(LEN), "-i", str(stem), "-af",
                        f"loudnorm=I=-18:TP=-1.5,afade=t=in:d=0.1,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
    rep = (v, s) in first; first.add((v, s))
    key[c] = {"pos": pos, "voice": v, "shift": s, "repeat": rep, "ladder1_sweet": L1[v]["sweet"], "rule_median": L1[v]["rule_median"]}
    data.append(c)
json.dump(key, open(OUT / "key.json", "w"), indent=1)      # compare with the stored blind/key.json
json.dump(data, open(OUT / "order.json", "w"))
print(len(data), "clips;", len(items), "distinct;", len(repeats), "repeats:", repeats)
