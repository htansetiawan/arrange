#!/usr/bin/env python3
"""make_clips.py (named Groban recheck): Groban only, sighted, each key named in canvas terms (piano key and octave).
The composer had heard Groban as natural at the canvas's key 0 (sung shift -12, one octave below the piano) and asked
to hear him again. The clips are the side-by-side ladder's Groban clips (-14 to -2), so no new audio was made.

    python3 make_clips.py      # ../build/groban-recheck/key.json and ladders.json, from the stored side-by-side key

The composer's answers on this page were not stored; the paper reports only that the recheck confirmed his
side-by-side pick for Groban (-10). These 7 clips are not counted in the 185.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "build/groban-recheck"; OUT.mkdir(parents=True, exist_ok=True)
key3 = json.load(open(HERE.parent / "side-by-side/key.json"))


def name(s):
    k = ((s + 6) % 12) - 6; o = (s - k) // 12
    return f"{s:+d}: piano key {k:+d}" + (", octave down" if o == -1 else "") + (" (the canvas 'key 0')" if s == -12 else "")


steps = sorted(((v["shift"], c) for c, v in key3.items() if v["voice"] == "groban"))
key = {c: {"voice": "groban", "shift": s} for s, c in steps}
json.dump(key, open(OUT / "key.json", "w"), indent=1)      # compare with the stored groban-recheck/key.json
json.dump([{"id": "groban", "label": "Groban", "steps": [c for _, c in steps], "names": [name(s) for s, _ in steps]}], open(OUT / "ladders.json", "w"), indent=1)
print([name(s) for s, _ in steps])
