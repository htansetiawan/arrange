#!/usr/bin/env python3
"""polish.py — a finished mix of the sung voice over the piano: vocal chain, shared reverb, bus glue, loudness (/arrange-render; analysis python with pedalboard + pyloudnorm).

    python polish.py --voice voice.mp3 --recording piano.wav --score sung-score.json --window 0 70 -o polished.mp3
    python polish.py ... --preset dry          # same level balance as mixcheck.py, no effects (an A/B reference)

The plain preview (mixcheck.py) adds the raw voice to the recording. A record does more:
the voice is cleaned (low cut, less mud, compressed so quiet syllables carry), brightened
(presence and air), and set in a space (a plate-like reverb with a short pre-delay so the
words stay in front, and a quiet tempo-free echo). The piano gets a small share of the
same space and a dip where the voice's consonants live, so the two sound recorded in one
room. The bus is glued with gentle compression, loudness-matched to -14 LUFS (streaming
level) and limited to -1 dBTP. The voice sits --voice-db over the piano on the sung
stretch, measured before the effects, as in mixcheck.py.

Presets: clean (the vocal chain, no added reverb: for a voice whose reference already carries a
room, which the singing model copies), light (default: the vocal chain and a small plate, as a channel strip in Logic would; the
piano untouched by reverb), touch (less still), warm and bright (much wetter; usually too
reverberant for a voice that should sit in front), dry (no effects).
"""
import argparse, json, subprocess, tempfile
from pathlib import Path

import numpy as np, soundfile as sf, librosa
import pyloudnorm as pyln
from pedalboard import (Pedalboard, HighpassFilter, LowpassFilter, PeakFilter, HighShelfFilter, LowShelfFilter,
                        Compressor, Reverb, Delay)

PRESETS = {   # verb_db / echo_db / piano_verb_db: return levels against the dry voice / piano (None = off)
    "light":  dict(room=0.42, damp=0.6, pre=0.03, verb_db=-20.0, echo=0.0, echo_db=None, piano_verb_db=None, air=1.5, presence=1.5),
    "clean":  dict(room=0.35, damp=0.6, pre=0.025, verb_db=None, echo=0.0, echo_db=None, piano_verb_db=None, air=1.5, presence=1.5),
    "touch":  dict(room=0.35, damp=0.6, pre=0.025, verb_db=-25.0, echo=0.0, echo_db=None, piano_verb_db=None, air=1.5, presence=1.5),
    "warm":   dict(room=0.72, damp=0.55, pre=0.035, verb_db=-9.0, echo=0.28, echo_db=-22.0, piano_verb_db=-17.0, air=2.0, presence=1.5),
    "bright": dict(room=0.55, damp=0.35, pre=0.025, verb_db=-11.0, echo=0.22, echo_db=-24.0, piano_verb_db=-19.0, air=3.0, presence=2.5),
}


def limit(x, sr, ceiling_db=-1.0, look_ms=3.0, release_ms=80.0):
    """A plain look-ahead peak limiter (pedalboard's Limiter adds make-up gain, which would undo the loudness match)."""
    from scipy.ndimage import minimum_filter1d
    c = 10 ** (ceiling_db / 20); peak = np.abs(x).max(axis=1)
    g = np.minimum(1.0, c / np.maximum(peak, 1e-9))
    w = max(1, int(look_ms / 1000 * sr)); g = minimum_filter1d(g, size=2 * w + 1)
    a = np.exp(-1.0 / (release_ms / 1000 * sr)); out = np.empty_like(g); cur = 1.0
    for i, gi in enumerate(g):                      # instant attack (the window looked ahead), smooth release
        cur = gi if gi < cur else a * cur + (1 - a) * gi; out[i] = cur
    return x * out[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True); ap.add_argument("--recording", required=True); ap.add_argument("--score", required=True)
    ap.add_argument("--window", type=float, nargs=2, required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--voice-db", type=float, default=6.0); ap.add_argument("--preset", default="light", choices=[*PRESETS, "dry"])
    ap.add_argument("--lufs", type=float, default=-14.0)
    a = ap.parse_args()
    rows = [r for r in json.load(open(a.score))["rows"] if r["kind"] == "note"]
    Y, sr = sf.read(a.recording, dtype="float32", always_2d=True)
    if Y.shape[1] == 1: Y = np.repeat(Y, 2, axis=1)
    n = len(Y)
    v, _ = librosa.load(a.voice, sr=sr, mono=True); v = np.pad(v, (0, max(0, n - len(v))))[:n].astype(np.float32)
    i0, i1 = int(rows[0]["t"] * sr), int(rows[-1]["end"] * sr)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2))) + 1e-9
    v *= rms(Y[i0:i1]) / rms(v[i0:i1]) * 10 ** (a.voice_db / 20)      # the same balance as the plain preview

    if a.preset == "dry":
        mix = Y + v[:, None]
    else:
        p = PRESETS[a.preset]
        chain = Pedalboard([
            HighpassFilter(90), LowShelfFilter(cutoff_frequency_hz=220, gain_db=-1.5),
            PeakFilter(cutoff_frequency_hz=350, gain_db=-2.0, q=1.0),           # mud
            Compressor(threshold_db=-22, ratio=3.0, attack_ms=6, release_ms=140),
            PeakFilter(cutoff_frequency_hz=3200, gain_db=p["presence"], q=0.8),  # words forward
            PeakFilter(cutoff_frequency_hz=7000, gain_db=-2.0, q=2.5),           # soft de-ess
            HighShelfFilter(cutoff_frequency_hz=10000, gain_db=p["air"]),       # air
        ])
        g = rms(v[i0:i1]); vc = chain(v[None, :], sr)[0]; vc *= g / rms(vc[i0:i1])   # keep the balance after the chain
        V = np.stack([vc, vc], axis=1)
        plate = Pedalboard([Delay(delay_seconds=p["pre"], feedback=0.0, mix=1.0), HighpassFilter(250), LowpassFilter(7500),
                            Reverb(room_size=p["room"], damping=p["damp"], wet_level=1.0, dry_level=0.0, width=1.0)])
        echo = Pedalboard([HighpassFilter(300), LowpassFilter(5000), Delay(delay_seconds=max(p["echo"], 0.01), feedback=0.25, mix=1.0)])
        vv = V.T.copy()
        wet = np.zeros_like(V) if p["verb_db"] is None else plate(vv, sr).T * 10 ** (p["verb_db"] / 20)
        if p["echo_db"] is not None: wet = wet + echo(vv, sr).T * 10 ** (p["echo_db"] / 20)
        piano = Pedalboard([PeakFilter(cutoff_frequency_hz=2800, gain_db=-1.5, q=0.9)])(Y.T.copy(), sr).T
        room = Pedalboard([HighpassFilter(200), Reverb(room_size=p["room"] * 0.8, damping=0.6, wet_level=1.0, dry_level=0.0, width=1.0)])
        pwet = 0 if p["piano_verb_db"] is None else room(Y.T.copy(), sr).T * 10 ** (p["piano_verb_db"] / 20)
        mix = (V + wet + piano + pwet).astype(np.float32)
        mix = Pedalboard([Compressor(threshold_db=-16, ratio=1.8, attack_ms=30, release_ms=250)])(mix.T.copy(), sr).T
    seg = mix[int(a.window[0] * sr):int(a.window[1] * sr)].astype(np.float64)
    meter = pyln.Meter(sr); seg = pyln.normalize.loudness(seg, meter.integrated_loudness(seg), a.lufs)
    seg = limit(seg, sr, ceiling_db=-1.0)
    fade = int(0.02 * sr); seg[-fade:] *= np.linspace(1, 0, fade)[:, None]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, seg, sr)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp.name, "-c:a", "libmp3lame", "-b:a", "192k", a.out], check=True)
    Path(tmp.name).unlink()
    print(f"POLISHED ({a.preset}): {a.out}; loudness {meter.integrated_loudness(seg.astype(np.float64)):.1f} LUFS")


if __name__ == "__main__":
    main()
