#!/usr/bin/env python3
"""verify.py — advisory measurements on rendered candidates (analysis python: librosa).

    python verify.py arrangement.json piano-analysis.json --spine piano.wav -o build/measurements.json

For every rendered candidate: in the layer's window, chroma agreement with
the piano (cosine similarity of mean chroma; evidence about pitch-class
content, NOT a certificate of harmony), RMS level against the piano in the
same window, and for score-route vocals the share of frames whose pYIN pitch
lies within 100 cents of the score's note (an estimator, vibrato and
portamento count against it). Every number carries its estimator and
window. No thresholds are applied and nothing is rejected here; the
creator's ear decides, and these numbers sit next to that decision in the
report. Leak detection (did an instrumental job add a voice?) is reported
as unmeasured.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
import arrangement as A  # noqa: E402


def chroma_mean(y, sr):
    c = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=2048)
    return c.mean(axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arrangement"); ap.add_argument("analysis"); ap.add_argument("--spine", required=True); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    plan = A.load(a.arrangement)
    sr = 22050
    piano, _ = librosa.load(a.spine, sr=sr, mono=True)
    out = {"estimators": {"chroma": "librosa chroma_cqt, hop 2048, cosine similarity of window means", "level": "RMS dB over the window, stem minus piano",
                          "pitch": "librosa pyin 60-1000 Hz, frame within 100 cents of the score note; vibrato counts against"}, "layers": {}}
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid)
        if not L.get("candidates"):
            out["layers"][lid] = {"status": "nothing rendered"}; continue
        i0, i1 = int(L["t0"] * sr), int(L["t1"] * sr)
        pw = piano[i0:i1]; pc = chroma_mean(pw, sr); prms = float(np.sqrt(np.mean(pw ** 2)) + 1e-9)
        rows = []
        score = Path(a.arrangement).parent / "jobs" / lid / "score.json"
        notes = [r for r in json.load(open(score))["rows"] if r["kind"] != "unsung"] if score.exists() else []
        for c in L["candidates"]:
            if c.get("status") != "rendered" or not c.get("path"):
                rows.append({"id": c["id"], "status": c.get("status")}); continue
            y, _ = librosa.load(c["path"], sr=sr, mono=True)
            y = np.pad(y, (0, max(0, len(piano) - len(y))))[:len(piano)]
            w = y[i0:i1]
            cc = chroma_mean(w, sr)
            sim = float(np.dot(pc, cc) / (np.linalg.norm(pc) * np.linalg.norm(cc) + 1e-9))
            level = float(20 * np.log10((np.sqrt(np.mean(w ** 2)) + 1e-9) / prms))
            row = {"id": c["id"], "window_s": [L["t0"], L["t1"]], "chroma_agreement_with_piano": round(sim, 3), "level_vs_piano_db": round(level, 1), "leak": "unmeasured"}
            if notes:
                import re as _re
                m_ = _re.search(r"([+-]\d+)$", str(c.get("label") or ""))   # labels end in the pitch shift: english-12, myvoice-12, shift+0
                shift = int(m_.group(1)) if m_ else 0
                f0, voiced, _ = librosa.pyin(y, fmin=60, fmax=1000, sr=sr, hop_length=512)
                times = librosa.times_like(f0, sr=sr, hop_length=512)
                hit, tot, worst = 0, 0, {}
                for r in notes:
                    m = (times >= r["t"]) & (times < r["end"]) & voiced
                    if not m.any():
                        continue
                    cents = 1200 * np.log2(f0[m] / librosa.midi_to_hz(r["pitch"] + shift))
                    ok = int((np.abs(cents) <= 100).sum()); hit += ok; tot += int(m.sum())
                    worst[r["word"] or "~"] = round(float(np.median(cents)), 0)
                row["pitch_within_100_cents"] = round(hit / tot, 3) if tot else None
                row["score_shift"] = shift
                row["voiced_share"] = round(float(voiced[int(L['t0'] * sr / 512):int(L['t1'] * sr / 512)].mean()), 3)
                row["largest_offsets_cents"] = dict(sorted(worst.items(), key=lambda kv: -abs(kv[1]))[:5])
            rows.append(row)
        out["layers"][lid] = {"candidates": rows}
        for r in rows:
            print(lid, json.dumps(r))
    json.dump(out, open(a.out, "w"), indent=1)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
