#!/usr/bin/env python3
"""stub.py — write a silent stem of EXACTLY the spine's length. Stdlib only.

    python3 stub.py --like takes/piano.wav -o stems/04_brass_STUB.wav
    python3 stub.py --seconds 214.31 --sr 48000 -o stems/04_brass_STUB.wav

A stub exists so the Logic session imports complete: one empty track per
undecided/blocked layer instead of a missing part. 24-bit PCM, same sample
rate and channel count as the spine (or 2 ch when given --seconds).
"""
import argparse, wave
from pathlib import Path


def spine_frames(path: Path):
    with wave.open(str(path), "rb") as w:
        return w.getnframes(), w.getframerate(), w.getnchannels()


def write_silence(out: Path, nframes: int, sr: int, ch: int = 2, width: int = 3):
    with wave.open(str(out), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(width); w.setframerate(sr)
        chunk = bytes(ch * width * 48000)
        left = nframes * ch * width
        while left > 0:
            n = min(left, len(chunk)); w.writeframesraw(chunk[:n]); left -= n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--like"); ap.add_argument("--seconds", type=float); ap.add_argument("--sr", type=int, default=48000)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    if a.like:
        n, sr, ch = spine_frames(Path(a.like))
    elif a.seconds:
        n, sr, ch = int(round(a.seconds * a.sr)), a.sr, 2
    else:
        ap.error("need --like or --seconds")
    write_silence(Path(a.out), n, sr, ch)
    print(f"wrote {a.out}: {n} frames @ {sr} Hz, {ch} ch, 24-bit silence")


if __name__ == "__main__":
    main()
