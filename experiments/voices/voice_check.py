#!/usr/bin/env python3
"""voice_check.py: does a rendered voice sound like the singer, and does it sing in tune? Needs resemblyzer and librosa.

    python3 voice_check.py voice-check/spec.json --base $ARRANGE_RUNS/color-purple/build -o build/voice-check.json

spec.json (paths relative to --base, default the spec's folder; "format" is the audio file suffix):
  {"score": "studio/sung-score.json", "skip": [[53.5, 58.6]], "window": [26, 68],
   "singers": {"henry": {"ref": ["../voices/henry-yard/pre/vocal", 31.5, 39.7],
                         "heldout": ["../voices/henry-yard/pre/vocal", 146.9, 156.8], "format": "wav"}},
   "renders": [{"name": "SoulX score mode", "singer": "henry", "file": "...", "format": "mp3", "start": 0, "shift": -12}, ...]}

Likeness: a speaker-verification model (Resemblyzer, GE2E) embeds each audio; the cosine
similarity between a render and the singer's held-out clip (a stretch the model never saw)
says how much it sounds like that person. The same clip against the reference clip gives
the "same person, different song moment" level to compare with. The sung source before
conversion gives the "nobody in particular" floor.
Pitch: each sung note's middle 60% is tracked (pYIN) and compared with the score note
(plus the render's octave shift): cents off, share within 50 cents (a quarter tone).
"""
import argparse, json, sys
from pathlib import Path

import librosa
import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav

SR = 16000


def load(path, a=None, b=None):
    y, _ = librosa.load(path, sr=SR, mono=True, offset=a or 0.0, duration=(b - a) if a is not None and b is not None else None)
    return y


def audio(base, path, fmt):
    return base / (f"{path}.{fmt}" if fmt else path)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--base", help="folder the spec's paths are relative to (default: the spec's folder)")
    a = ap.parse_args()
    spec = json.load(open(a.spec)); base = Path(a.base) if a.base else Path(a.spec).parent
    enc = VoiceEncoder(verbose=False)
    emb = lambda y: enc.embed_utterance(preprocess_wav(y, source_sr=SR))
    rows = [r for r in json.load(open(base / spec["score"]))["rows"] if r["kind"] == "note"
            and not any(s0 <= r["t"] <= s1 for s0, s1 in spec.get("skip", []))]
    singers = {}
    for name, s in spec["singers"].items():
        f = s.get("format")
        e_ref = emb(load(audio(base, s["ref"][0], f), s["ref"][1], s["ref"][2])); e_ho = emb(load(audio(base, s["heldout"][0], f), s["heldout"][1], s["heldout"][2]))
        singers[name] = {"ref": e_ref, "heldout": e_ho, "ref_vs_heldout": float(e_ref @ e_ho)}
    out = {"singers": {k: {"ref_vs_heldout": round(v["ref_vs_heldout"], 3)} for k, v in singers.items()}, "renders": []}
    for r in spec["renders"]:
        y = load(audio(base, r["file"], r.get("format"))); st = r.get("start", 0.0)   # the file's time 0 = recording time `start`
        w0, w1 = spec.get("window", [26, 68])
        seg = y[int(max(0, w0 - st) * SR):int((w1 - st) * SR)]
        e = emb(seg); s = singers[r["singer"]]
        f0, vflag, _ = librosa.pyin(seg, fmin=65, fmax=1000, sr=SR, frame_length=1024, hop_length=160)
        tt = np.arange(len(f0)) * 160 / SR + max(w0, st)
        cents = []
        for n in rows:
            if not (w0 <= n["t"] and n["end"] <= w1):
                continue
            d = n["end"] - n["t"]; m = (tt >= n["t"] + 0.2 * d) & (tt <= n["end"] - 0.2 * d) & ~np.isnan(f0)
            if m.sum() < 3:
                continue
            sung = 12 * np.log2(np.median(f0[m]) / 440) + 69
            cents.append(100 * (sung - (n["pitch"] + r.get("shift", 0))))
        c = np.abs(np.array(cents))
        out["renders"].append({"name": r["name"], "singer": r["singer"], "like_heldout": round(float(e @ s["heldout"]), 3), "like_ref": round(float(e @ s["ref"]), 3),
                               "notes": len(c), "in_tune_50c": round(float((c <= 50).mean()), 2) if len(c) else None,
                               "median_cents_off": round(float(np.median(c)), 1) if len(c) else None})
        print(json.dumps(out["renders"][-1]))
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out["singers"]))


if __name__ == "__main__":
    main()
