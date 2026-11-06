#!/usr/bin/env python3
"""measure_clips.py: pitch track (RMVPE, on the CPU) of each clip the composer heard, the exact 15 s.

    ARRANGE_SOULX=/path/to/SoulX-Singer python3 measure_clips.py build/pilot/clips build/f0/pilot
    ARRANGE_SOULX=/path/to/SoulX-Singer python3 measure_clips.py build/blind/clips build/f0/blind

Writes <out>/<code>.npy (Hz, 50 frames a second, 0 = unvoiced), which render_pitch.py reads. Runs in SoulX-Singer's
Python environment and uses its preprocessing RMVPE checkpoint
(pretrained_models/SoulX-Singer-Preprocess/rmvpe/rmvpe.pt). Decoded audio is written only to a temporary folder.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

clips, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(); out.mkdir(parents=True, exist_ok=True)
SX = os.environ["ARRANGE_SOULX"]; sys.path.insert(0, SX); os.chdir(SX)
from preprocess.tools.f0_extraction import F0Extractor  # noqa: E402

MP3, WAV = "mp3", "wav"
f = F0Extractor(model_path="pretrained_models/SoulX-Singer-Preprocess/rmvpe/rmvpe.pt", device="cpu")
with tempfile.TemporaryDirectory(prefix="ladder-f0-") as tmp:
    for clip in sorted(clips.glob(f"*.{MP3}")):
        dst = out / f"{clip.stem}.npy"
        if dst.exists():
            continue
        wav = Path(tmp) / f"{clip.stem}.{WAV}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-ac", "1", "-ar", "24000", str(wav)], check=True)
        f.process(str(wav), f0_path=str(dst)); wav.unlink(); print(clip.stem, flush=True)
