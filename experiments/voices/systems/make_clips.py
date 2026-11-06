#!/usr/bin/env python3
"""make_clips.py: cut the clips of the system comparison (Section 5.3). The same 15 s excerpts as the 5.4 rating set,
the same mixing for every clip; SoulX and Seed-VC paired on song, singer and key; TechSinger's three built-in singers on
every song; one hidden repeat per system.

    python3 make_clips.py    # ../build/systems/clips/, key.json (needs ../build/systems/manifest.json from render_systems.py)

The author's own voice on Color Purple (voice id henry-yard) is the SoulX / Seed-VC pair rendered earlier for the song
(own-score and own-seedvc, under $ARRANGE_RUNS/color-purple/build/polished/). The key the rating page hid from the
composer is stored as key.json in this folder, with each mix named by its file stem. The rated set also held clips of
a song that is not distributed (their codes are left out of key.json), so a rerun on these songs draws different codes.
"""
import json, os, random, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs"))
OUT = HERE.parent / "build/systems"; MP3 = "mp3"
EXCERPT = {"all-the-things-cohen": (0, 48.8), "color-purple": (0, 27.0), "someday-my-prince": (0, 11.3)}
LEN = 15.0
items = [{k: m[k] for k in ("song", "system", "voice", "shift", "mix")} for m in json.load(open(OUT / "manifest.json"))]
# Color Purple, the author's own voice: the SoulX / Seed-VC pair rendered earlier (already mixed the same way)
items += [{"song": "color-purple", "system": "SoulX", "voice": "henry-yard", "shift": -12, "mix": str(RUNS / f"color-purple/build/polished/own-score.{MP3}")},
          {"song": "color-purple", "system": "Seed-VC", "voice": "henry-yard", "shift": -12, "mix": str(RUNS / f"color-purple/build/polished/own-seedvc.{MP3}")}]
rng = random.Random(3112026)
for sysname in ("SoulX", "Seed-VC", "TechSinger"):     # one hidden repeat per system
    rep = dict(rng.choice([i for i in items if i["system"] == sysname])); rep["repeat"] = True; items.append(rep)
for _ in range(10000):
    rng.shuffle(items)
    first = {}
    ok = all((first.setdefault(i["mix"], n) == n) or n - first[i["mix"]] >= 8 for n, i in enumerate(items))
    if ok: break
codes = rng.sample([f"{a}{b}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in "23456789"], len(items))
(OUT / "clips").mkdir(parents=True, exist_ok=True)
key, order = {}, []
for c, it in zip(codes, items):
    w0, st = EXCERPT[it["song"]]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{st - w0:.3f}", "-t", str(LEN), "-i", it["mix"], "-af",
                    f"afade=t=in:d=0.15,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "96k", str(OUT / "clips" / f"{c}.{MP3}")], check=True)
    key[c] = {**it, "repeat": it.get("repeat", False)}; order.append(c)
json.dump({c: {**k, "mix": Path(k["mix"]).stem} for c, k in key.items()}, open(OUT / "key.json", "w"), indent=1)   # compare with systems/key.json
json.dump(order, open(OUT / "order.json", "w"))
print(len(order), "clips:", {s: sum(1 for k in key.values() if k["system"] == s and not k["repeat"]) for s in ("SoulX", "Seed-VC", "TechSinger")})
