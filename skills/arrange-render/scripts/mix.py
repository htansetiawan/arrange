#!/usr/bin/env python3
"""mix.py — a listening preview: the piano plus one candidate per layer (analysis python).

    python mix.py arrangement.json --spine piano.wav -o preview.mp3 [--window 68 118] [--pick L2=L2c2 ...] [--gain L1=-3 ...]

Uses each layer's chosen candidate unless --pick names another; stubs and
unrendered layers are silent. Levels are equal-ish (each stem matched to the
piano's RMS over its own window, then the layer's gain_db), the mix is
peak-limited to -0.3 dBFS, and the window is cut before MP3 encoding so the
creator hears just the passage. A preview, never the deliverable.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
import arrangement as A  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arrangement"); ap.add_argument("--spine", required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--window", type=float, nargs=2); ap.add_argument("--pick", action="append", default=[]); ap.add_argument("--gain", action="append", default=[])
    a = ap.parse_args()
    plan = A.load(a.arrangement)
    picks = dict(p.split("=", 1) for p in a.pick); gains = {k: float(v) for k, v in (g.split("=", 1) for g in a.gain)}
    piano, sr = sf.read(a.spine, dtype="float32", always_2d=True); n = len(piano)
    mix = piano.copy(); used = []
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid)
        want = picks.get(lid, L.get("chosen"))
        c = next((c for c in L.get("candidates", []) if c["id"] == want and c.get("path")), None)
        if not c:
            used.append(f"{lid} {L['name']}: silent ({'stub' if L['kind'] == 'stub' else 'no candidate'})"); continue
        y, _ = librosa.load(c["path"], sr=sr, mono=True); y = np.pad(y, (0, max(0, n - len(y))))[:n]
        i0, i1 = int(L["t0"] * sr), int(L["t1"] * sr)
        prms = float(np.sqrt(np.mean(piano[i0:i1] ** 2)) + 1e-9); yrms = float(np.sqrt(np.mean(y[i0:i1] ** 2)) + 1e-9)
        g = prms / yrms * 10 ** ((gains.get(lid, L.get("gain_db", 0.0)) - 3.0) / 20)
        mix[:, 0] += y * g; mix[:, 1] += y * g
        used.append(f"{lid} {L['name']}: {c['id']} ({c.get('label', '')}) at {20 * np.log10(g):+.1f} dB")
    mix *= min(1.0, 10 ** (-0.3 / 20) / float(np.abs(mix).max()))
    if a.window:
        mix = mix[int(a.window[0] * sr):int(a.window[1] * sr)]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, mix, sr); subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp.name, "-c:a", "libmp3lame", "-b:a", "192k", a.out], check=True)
    Path(tmp.name).unlink()
    print(f"wrote {a.out}: " + "; ".join(used))


if __name__ == "__main__":
    main()
