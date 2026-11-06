#!/usr/bin/env python3
"""mixcheck.py — where the sung voice actually enters at each line start, and the voice mixed over the recording (analysis python).

    python mixcheck.py --voice voice.mp3 --score score.json --recording piano.wav --window 0 70 -o mix.mp3 --report entries.json

An entry is the first moment, from 0.6 s before to 1 s after a line's first note, at which the voice's
RMS over the last 93 ms is above -30 dBFS. A voice well above that level reads within a few ms of its
true start; a voice near -30 dB reads later (the window must fill before it crosses).
"""
import argparse, json, subprocess, tempfile
from pathlib import Path

import numpy as np, soundfile as sf, librosa

FRAME, HOP = 2048, 64   # RMS window (93 ms at 22.05 kHz) and step (2.9 ms): the entry is read to within a few ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True); ap.add_argument("--score", required=True); ap.add_argument("--recording", required=True)
    ap.add_argument("--window", type=float, nargs=2, required=True); ap.add_argument("-o", "--out", required=True); ap.add_argument("--report", required=True)
    ap.add_argument("--voice-db", type=float, default=6.0, help="voice level against the piano over the sung stretch, dB (positive = voice in front, piano behind)")
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.score))["rows"] if r["kind"] == "note"]
    allrows = json.load(open(a.score))["rows"]
    starts = [r for i, r in enumerate(rows) if i == 0 or r["t"] - rows[i - 1]["end"] >= 1.0 or
              (r["t"] - rows[i - 1]["t"] >= 1.5 and r.get("word") and r.get("word")[:1].isupper())]
    joined = {round(r["t"], 3) for i, r in enumerate(allrows) if i and abs(allrows[i - 1]["end"] - r["t"]) < 0.02 and allrows[i - 1]["pitch"] == r["pitch"]}
    y, sr = librosa.load(a.voice, sr=22050, mono=True); rms = librosa.feature.rms(y=y, frame_length=FRAME, hop_length=HOP)[0]
    # librosa centres each frame on its time stamp, so a frame stamped t already holds FRAME/2 samples after t
    # (46 ms here) and crosses the threshold before the voice arrives. Stamp each frame at its trailing edge,
    # the moment all its samples have sounded, so an entry is never read before the sound that caused it.
    db = 20 * np.log10(rms + 1e-9); tt = librosa.times_like(rms, sr=sr, hop_length=HOP) + FRAME / 2 / sr
    entries = []
    for r in starts:
        k = np.where((tt > r["t"] - 0.6) & (tt < r["t"] + 1.0) & (db > -30))[0]
        got = float(tt[k[0]]) if len(k) else None
        if round(r["t"], 3) in joined:
            entries.append({"word": r.get("word") or r["text"], "score_s": round(r["t"], 3), "voice_s": None, "off_ms": None, "joined": True}); continue
        entries.append({"word": r.get("word") or r["text"], "score_s": round(r["t"], 3), "voice_s": None if got is None else round(got, 3),
                        "off_ms": None if got is None else int(round((got - r["t"]) * 1000))})
    Y, sr2 = sf.read(a.recording, dtype="float32", always_2d=True); n = len(Y)
    v, _ = librosa.load(a.voice, sr=sr2, mono=True); v = np.pad(v, (0, max(0, n - len(v))))[:n]
    i0, i1 = int(rows[0]["t"] * sr2), int(rows[-1]["end"] * sr2)
    g = float(np.sqrt(np.mean(Y[i0:i1] ** 2))) / (float(np.sqrt(np.mean(v[i0:i1] ** 2))) + 1e-9) * 10 ** (a.voice_db / 20)
    mix = Y.copy(); mix[:, 0] += v * g; mix[:, 1] += v * g; mix *= min(1.0, 0.97 / np.abs(mix).max())
    seg = mix[int(a.window[0] * sr2):int(a.window[1] * sr2)]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, seg, sr2)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp.name, "-c:a", "libmp3lame", "-b:a", "192k", a.out], check=True)
    Path(tmp.name).unlink()
    json.dump({"voice": a.voice, "entries": entries}, open(a.report, "w"), indent=1)
    for e in entries:
        if e.get("joined"):
            print(f"ENTRY: '{e['word']}' score {e['score_s']:.2f} s, joined to the note before it (same pitch, no gap)"); continue
        print(f"ENTRY: '{e['word']}' score {e['score_s']:.2f} s, voice {e['voice_s'] if e['voice_s'] is not None else 'silent'}" + (f" ({e['off_ms']:+d} ms)" if e['off_ms'] is not None else ""))
    print("MIX:", a.out)


if __name__ == "__main__":
    main()
