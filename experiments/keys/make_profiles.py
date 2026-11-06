#!/usr/bin/env python3
"""make_profiles.py: the measurements every key analysis reads, written to data/profiles.json.

    ARRANGE_RUNS=/path/to/runs python3 make_profiles.py

Inputs (not distributed): each singer's pitch track (`$ARRANGE_RUNS/color-purple/voices/<voice>/pre/vocal_f0.npy`, from
the separated whole recording; Groban has none, so his notes come from the reference clip's `prompt.json`) and the
fitted score of each song (`$ARRANGE_RUNS/<song>/plan/fit/fit.json`). The four rules are computed by the skill's own
`skills/arrange-lyrics/scripts/center.py`.

Output, per voice: where the numbers come from, seconds sung, the 10/25/50/75/90th percentile notes, the reference
clip's median note, every percentile from 1 to 99 (for choosing the percentile on the pilot) and the share of sung time
below each note (for the pilot table); per song: note count, 10/50/90th percentile, lowest and highest note; per case:
the key each rule gives. No pitch track and no note of any song is stored.
"""
import json, os, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUNS = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[1] / "runs"))
sys.path.insert(0, str(HERE.parents[1] / "skills/arrange-lyrics/scripts"))
import center as C  # noqa: E402

VOICES = RUNS / "color-purple/voices"
SONGS = {"attya": ("All the Things You Are", "all-the-things-cohen"), "someday": ("Someday My Prince Will Come", "someday-my-prince")}
CASES = [("attya", v) for v in ["groban", "adams", "clarkson", "ariana", "jackson", "bolton", "wonder", "buble"]] + \
        [("someday", "clarkson"), ("someday", "ariana")]
fit = lambda s: RUNS / SONGS[s][1] / "plan/fit/fit.json"

prof = {"voices": {}, "songs": {}, "rules": {}}
for v in sorted({v for _, v in CASES}):
    vd = VOICES / v; p = C.voice_profile(vd); f0 = vd / "pre/vocal_f0.npy"
    m = C.midi(np.load(f0)) if f0.exists() else C.clip_notes(vd / "prompt.json")
    dist = m[(m > np.percentile(m, 1)) & (m < np.percentile(m, 99))]       # the same trim as center.voice_profile
    prof["voices"][v] = {"source": "whole recording" if f0.exists() else "reference clip only", "seconds_sung": round(len(m) / C.FPS, 1),
                         **{k: (None if p[k] is None else float(p[k])) for k in ("p10", "p25", "median", "p75", "p90", "clip_median")},
                         "percentiles_1_to_99": [float(x) for x in np.percentile(dist, range(1, 100))],
                         "share_below": {str(n): float((dist < n).mean()) for n in range(40, 90)}}
for s, (title, _) in SONGS.items():
    sp = C.song_profile(fit(s))
    prof["songs"][s] = {"title": title, **{k: (float(x) if isinstance(x, (float, np.floating)) else int(x)) for k, x in sp.items()}}
for s, v in CASES:
    prof["rules"][f"{s}/{v}"] = C.recommend(C.voice_profile(VOICES / v), C.song_profile(fit(s)))
(HERE / "data/profiles.json").write_text(json.dumps(prof, indent=1, ensure_ascii=False) + "\n")
print("wrote data/profiles.json:", len(prof["voices"]), "voices,", len(prof["songs"]), "songs,", len(prof["rules"]), "cases")
