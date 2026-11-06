#!/usr/bin/env python3
"""hear.py — take the melody from a sung reference instead of asking the composer to write it (/arrange-lyrics; a Python with demucs and librosa).

    python hear.py --reference demo.mp3 --analysis piano-analysis.json --window 88 140 -o jobs/L1/heard.json [--expect "F4 Bb4 Bb4 C5 ..."] [--device cpu]

Separates the voice (Demucs htdemucs_6s), tracks its pitch (pYIN), cuts the
track into notes (voiced runs, a new note where the pitch moves a semitone or
more for 60 ms), rounds each note to the nearest semitone, and snaps starts
and ends to the piano's grid at half-beats of the measured map (the composer's
notation is twice the map's tempo, so a half-beat here is the composer's quarter). With
--expect, the composer's own pitch sequence is aligned to the heard notes and
disagreements are listed. Output: rows in the fit format (no words yet) and a
report. Temporary lossless stems are deleted; the voice stem is kept as MP3.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent)); import arrange_config  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
FLAT = {"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10, "C#": 1, "D#": 3, "F#": 6, "G#": 8, "A#": 10}


def midi_of(name):
    import re
    m = re.fullmatch(r"([A-G])([#b]?)(\d)", name.strip())
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    acc = {"#": 1, "b": -1, "": 0}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + base + acc


def separate(ref, out_dir, device="cuda"):
    import demucs.separate
    demucs.separate.main(["-n", "htdemucs_6s", "--two-stems", "vocals", "-o", str(out_dir), "-d", device, str(ref)])
    cand = list(Path(out_dir).glob("htdemucs_6s/*/vocals.wav"))
    return cand[0]


def notes_from_f0(times, f0, voiced, prob, min_dur=0.08):
    notes, cur = [], None
    for t, f, v, p in zip(times, f0, voiced, prob):
        if not v or not np.isfinite(f) or p < 0.5:
            if cur:
                notes.append(cur); cur = None
            continue
        m = 69 + 12 * np.log2(f / 440.0)
        if cur is None:
            cur = {"t": t, "end": t, "m": [m]}
        elif abs(m - np.median(cur["m"][-6:])) >= 0.8 and len(cur["m"]) >= 6:
            notes.append(cur); cur = {"t": t, "end": t, "m": [m]}
        else:
            cur["end"] = t; cur["m"].append(m)
    if cur:
        notes.append(cur)
    out = []
    for n in notes:
        dur = n["end"] - n["t"]
        if dur < min_dur:
            continue
        out.append({"t": round(float(n["t"]), 3), "end": round(float(n["end"]) + 0.02, 3), "pitch": int(round(float(np.median(n["m"])))), "cents": round(float((np.median(n["m"]) - round(np.median(n["m"]))) * 100))})
    # merge same-pitch notes separated by less than 60 ms (vibrato splits)
    merged = []
    for n in out:
        if merged and n["pitch"] == merged[-1]["pitch"] and n["t"] - merged[-1]["end"] < 0.06:
            merged[-1]["end"] = n["end"]
        else:
            merged.append(n)
    return merged


def snap(rows, clk, division=2):
    """Snap starts and ends to the map's grid at `division` steps per beat; keep at least one step of length."""
    grid = []
    for i, b in enumerate(clk.beats):
        nxt = clk.beats[i + 1]["t"] if i + 1 < len(clk.beats) else b["t"] + clk.last_dur
        for k in range(division):
            grid.append((b["t"] + (nxt - b["t"]) * k / division, b["bar"], b["beat"] + k / division))
    g = np.array([x[0] for x in grid])
    def near(t):
        return int(np.argmin(np.abs(g - t)))
    out = []
    for r in rows:
        i0 = near(r["t"]); i1 = near(r["end"])
        if i1 <= i0:
            i1 = min(i0 + 1, len(grid) - 1)
        out.append({**r, "t_heard": r["t"], "end_heard": r["end"], "t": round(float(grid[i0][0]), 3), "end": round(float(grid[i1][0]), 3), "bar": grid[i0][1], "beat": round(grid[i0][2], 2),
                    "snap_ms": int(round(1000 * abs(grid[i0][0] - r["t"])))})
    # no overlaps after snapping
    for a, b in zip(out, out[1:]):
        if a["end"] > b["t"]:
            a["end"] = b["t"]
    return [r for r in out if r["end"] > r["t"]]


def align(expected, heard):
    n, m = len(expected), len(heard); INF = 1e9
    D = np.full((n + 1, m + 1), INF); D[0, 0] = 0; B = np.zeros((n + 1, m + 1), dtype=np.int8)
    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            best, arg = INF, 0
            if i and j:
                d = abs(expected[i - 1] - heard[j - 1]); c = 0 if d == 0 else 0.4 if d % 12 == 0 else 1.0 if d <= 2 else 1.5
                if D[i - 1, j - 1] + c < best:
                    best, arg = D[i - 1, j - 1] + c, 1
            if i and D[i - 1, j] + 1.0 < best:
                best, arg = D[i - 1, j] + 1.0, 2
            if j and D[i, j - 1] + 0.7 < best:
                best, arg = D[i, j - 1] + 0.7, 3
            D[i, j], B[i, j] = best, arg
    i, j, pairs = n, m, []
    while i or j:
        if B[i, j] == 1:
            pairs.append((i - 1, j - 1)); i, j = i - 1, j - 1
        elif B[i, j] == 2:
            pairs.append((i - 1, None)); i -= 1
        else:
            pairs.append((None, j - 1)); j -= 1
    return list(reversed(pairs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--window", type=float, nargs=2, required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--expect"); ap.add_argument("--division", type=int, default=2); ap.add_argument("--keep-voice-mp3")
    ap.add_argument("--vocals-wav", help="reuse an already separated voice stem")
    ap.add_argument("--device", help="cuda or cpu for Demucs (default: the ARRANGE device setting)")
    a = ap.parse_args()
    a.device = a.device or arrange_config.get(arrange_config.load(), "device", "cuda")
    clk = Clock(json.load(open(a.analysis)))
    with tempfile.TemporaryDirectory(prefix="hear-") as tmp:
        voc = Path(a.vocals_wav) if a.vocals_wav else separate(a.reference, tmp, a.device)
        y, sr = librosa.load(str(voc), sr=22050, mono=True, offset=a.window[0], duration=a.window[1] - a.window[0])
        if a.keep_voice_mp3:
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(a.window[0]), "-t", str(a.window[1] - a.window[0]), "-i", str(voc), "-c:a", "libmp3lame", "-b:a", "160k", a.keep_voice_mp3], check=True)
    hop = 256
    f0, voiced, prob = librosa.pyin(y, fmin=70, fmax=700, sr=sr, hop_length=hop, frame_length=2048)
    times = librosa.times_like(f0, sr=sr, hop_length=hop) + a.window[0]
    heard = notes_from_f0(times, f0, voiced, prob)
    snapped = snap(heard, clk, a.division)
    report = [f"{len(heard)} sung notes heard between {a.window[0]}s and {a.window[1]}s; snapped to {a.division} steps per beat of the map; median snap {int(np.median([r['snap_ms'] for r in snapped]))} ms"]
    if a.expect:
        exp = [midi_of(x) for x in a.expect.split()]
        pairs = align(exp, [r["pitch"] for r in snapped])
        agree = sum(1 for i, j in pairs if i is not None and j is not None and exp[i] == snapped[j]["pitch"])
        octv = sum(1 for i, j in pairs if i is not None and j is not None and exp[i] != snapped[j]["pitch"] and (exp[i] - snapped[j]["pitch"]) % 12 == 0)
        diffs = [(NAMES[exp[i] % 12] + str(exp[i] // 12 - 1), NAMES[snapped[j]["pitch"] % 12] + str(snapped[j]["pitch"] // 12 - 1), snapped[j]["t"]) for i, j in pairs if i is not None and j is not None and exp[i] != snapped[j]["pitch"]]
        missing = [NAMES[exp[i] % 12] + str(exp[i] // 12 - 1) for i, j in pairs if j is None]
        extra = [(NAMES[snapped[j]["pitch"] % 12] + str(snapped[j]["pitch"] // 12 - 1), snapped[j]["t"]) for i, j in pairs if i is None]
        report.append(f"against the composer's {len(exp)} pitches: {agree} agree, {octv} differ by an octave, {len(diffs) - octv} differ otherwise, {len(missing)} of theirs are not heard, {len(extra)} heard notes are not in the written list")
        if diffs:
            report.append("differences (written, heard, time): " + "; ".join(f"{h} vs {g} at {t}s" for h, g, t in diffs[:12]))
        if missing:
            report.append("written notes not heard: " + " ".join(missing))
        if extra:
            report.append("heard but not in the written list: " + "; ".join(f"{p} at {t}s" for p, t in extra[:12]))
        for i, j in pairs:
            if i is not None and j is not None:
                snapped[j]["composer_pitch"] = exp[i]
    rows = [{"index": k, "t": r["t"], "end": r["end"], "pitch": r["pitch"], "bar": r["bar"], "beat": r["beat"], "text": "", "kind": "unsung", "word": None,
             "placed": f"heard in the reference at {r['t_heard']}s (snapped {r['snap_ms']} ms)", "cents": r["cents"], "composer_pitch": r.get("composer_pitch")} for k, r in enumerate(snapped)]
    json.dump({"reference": a.reference, "window": a.window, "rows": rows, "report": report}, open(a.out, "w"), indent=1)
    for r in report:
        print("HEARD:", r)
    print(" ".join(f"{NAMES[r['pitch'] % 12]}{r['pitch'] // 12 - 1}@{r['t']:.1f}" for r in rows))


if __name__ == "__main__":
    main()
