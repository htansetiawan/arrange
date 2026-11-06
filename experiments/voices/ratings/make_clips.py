#!/usr/bin/env python3
"""make_clips.py: cut the blind rating set of Section 5.4. One 15 s excerpt per (song, voice), the same excerpt for
every voice of a song, shuffled under neutral codes, with hidden repeats to measure how consistent the rater is.

    ARRANGE_RUNS=/path/to/runs python3 make_clips.py      # ../build/ratings/clips/, key.json, order.json

Needs each song project's mixes (the paths in SONGS, under $ARRANGE_RUNS) and ffmpeg with libmp3lame. The key the
rating page hid from the composer is stored as key.json in this folder. The rated set also held clips of songs that
are not distributed (their codes are left out of key.json), so a rerun on these songs draws different codes.
"""
import json, os, random, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[2] / "runs"))
OUT = HERE.parent / "build/ratings"; MP3 = "mp3"
LEN = 15.0
# song: (mix window start in the source, excerpt start in the source, {voice: mix path})
SONGS = {
    "all-the-things": (0, 48.8, {v: f"all-the-things-cohen/build/pills/{v}" for v in
                                 ["groban", "henry", "buble", "jackson", "wonder", "ariana", "clarkson", "bolton", "adams"]}),
    "color-purple": (0, 27.0, {v: f"color-purple/build/polished/{v}" for v in
                               ["groban", "own-seedvc", "own-score", "pavarotti", "bolton", "adams"]}),
    "someday": (0, 11.3, {"groban": "someday-my-prince/build/studio/voice-mix-groban",
                          **{v: f"someday-my-prince/build/polished/{v}" for v in ["mine", "ariana", "clarkson", "bolton", "adams"]}}),
}
REPEATS = [("all-the-things", "groban"), ("color-purple", "pavarotti"), ("someday", "mine")]

items = [(s, v) for s, (_, _, vs) in SONGS.items() for v in vs] + REPEATS
rng = random.Random(20261103)
for _ in range(10000):                      # shuffle until repeats sit at least 8 apart from their twin
    rng.shuffle(items)
    pos = {}
    ok = True
    for i, it in enumerate(items):
        if it in pos and i - pos[it] < 8: ok = False; break
        pos.setdefault(it, i)
    if ok: break
codes = rng.sample([f"{a}{b}" for a in "BCDFGHJKLMNPRSTVWXZ" for b in range(2, 10)], len(items))
(OUT / "clips").mkdir(parents=True, exist_ok=True)
key, order = {}, []
for code, (s, v) in zip(codes, items):
    win, start, vs = SONGS[s]
    src = RUNS / f"{vs[v]}.{MP3}"
    out = OUT / "clips" / f"{code}.{MP3}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start - win:.3f}", "-t", f"{LEN}", "-i", str(src),
                    "-af", f"afade=t=in:d=0.15,afade=t=out:st={LEN - 0.8}:d=0.8", "-c:a", "libmp3lame", "-b:a", "96k", str(out)], check=True)
    key[code] = {"song": s, "voice": v, "mix": vs[v], "source_start": start, "length": LEN,
                 "repeat": (s, v) in REPEATS and sum(1 for c in key.values() if (c["song"], c["voice"]) == (s, v)) > 0}
    order.append(code)
json.dump(key, open(OUT / "key.json", "w"), indent=1)       # compare with the stored ratings/key.json
json.dump(order, open(OUT / "order.json", "w"))
print(len(order), "clips;", sum(k["repeat"] for k in key.values()), "repeats")
