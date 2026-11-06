#!/usr/bin/env python3
"""finetune_data.py: list and time the clips the converter was fine-tuned on. Reads audio headers only; needs soundfile.

    python3 finetune_data.py DATASET_DIR        # ../build/finetune-clips.json: clip name, seconds, sample rate

DATASET_DIR is the Seed-VC training folder: three recordings of the author singing his own produced songs, with the
vocal separated and cut into short clips by the preprocessing step, named <recording>_vocal_<n>. The paper's dataset
held 113 clips (recordings henry-yard_pre, henry-sung_pre1 and henry-sung_pre2).
"""
import json, sys
from pathlib import Path

import soundfile as sf

ds = Path(sys.argv[1]); rows = []
for f in sorted(ds.iterdir()):
    try:
        i = sf.info(str(f))
    except RuntimeError:
        continue                                         # not an audio file
    rows.append({"clip": f.stem, "seconds": round(i.duration, 3), "sr": i.samplerate})
tot = sum(r["seconds"] for r in rows)
print(f"{len(rows)} clips, {tot:.1f} s = {tot / 60:.1f} min")
out = Path(__file__).resolve().parents[1] / "build/finetune-clips.json"; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(rows, indent=1) + "\n")   # compare with the stored finetune-clips.json
