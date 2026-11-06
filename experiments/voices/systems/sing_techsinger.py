#!/usr/bin/env python3
"""sing_techsinger.py: sing a sung score with TechSinger instead of SoulX-Singer (TechSinger's Python environment).

TechSinger (Guo et al., AAAI 2025) is trained on GTSinger. It sings from the score (phonemes with a note pitch,
note duration and note type each) in one of its own trained singers: it cannot copy a reference voice.
English singers: EN-Alto-1, EN-Alto-2, EN-Tenor-1. This runner takes the same sung score SoulX gets
(build/.../sung-score.json: one row per note, ARPAbet phonemes already split by syllable, slurs marked), so the two
singers are compared on identical input. Timing is forced from the score (the model's own
duration predictor sang the right pitches at the wrong tempo in an earlier test): consonants 60 ms or less, the vowel holds the rest
of the note. Phrases are split at gaps of --gap seconds or more and each is placed at its first note's time, so the
output is a full-length stem aligned to the recording, like SoulX's.

  cd $ARRANGE_TECHSINGER && PYTHONPATH=. $ARRANGE_TS_PY <this file> sung-score.json --singer EN-Tenor-1 --shift 0 \\
      --length 267 -o <stem>

ARRANGE_TECHSINGER is the TechSinger checkout with its checkpoints (default: the current folder).
"""
import argparse
import json
import os
import sys
from pathlib import Path

TS = Path(os.environ.get("ARRANGE_TECHSINGER", ".")).resolve()
SPK = {"EN-Alto-1": 35, "EN-Alto-2": 36, "EN-Tenor-1": 37}
ap = argparse.ArgumentParser()
ap.add_argument("score"); ap.add_argument("-o", "--out", required=True)
ap.add_argument("--singer", default="EN-Tenor-1", choices=sorted(SPK)); ap.add_argument("--shift", type=int, default=0)
ap.add_argument("--gap", type=float, default=0.6, help="a gap of this many seconds or more starts a new phrase")
ap.add_argument("--length", type=float, default=None, help="stem length in seconds (default: last note + 2 s)")
A = ap.parse_args()
A.score, A.out = os.path.abspath(A.score), os.path.abspath(A.out)
os.chdir(TS); sys.path.insert(0, str(TS)); sys.argv = [sys.argv[0]]   # TechSinger's hparams parse argv on import
REST = 0.12


def phrases(rows, gap):
    out = [[]]
    for r in rows:
        if out[-1] and r["t"] - out[-1][-1]["end"] >= gap:
            out.append([])
        out[-1].append(r)
    return [p for p in out if p]


def build(ph_rows, spk, shift, phone_set):
    ph, notes, durs, types, phd = [], [], [], [], []
    last_vowel, prev_end = None, ph_rows[0]["t"]
    for r in ph_rows:
        gap = r["t"] - prev_end
        if gap >= REST:
            ph.append("<SP>"); notes.append(0); durs.append(round(gap, 4)); types.append(1); phd.append(round(gap, 4))
        dur = round(r["end"] - r["t"] + (gap if 0 < gap < REST else 0), 4)
        pitch = r["pitch"] + shift
        phones = [p for p in (r.get("phoneme") or "").replace("en_", "").split("-") if p]
        if r["kind"] == "slur" or not phones:
            if last_vowel:
                ph.append(last_vowel); notes.append(pitch); durs.append(dur); types.append(3); phd.append(dur)
        else:
            cons = [p for p in phones if not p[-1].isdigit()]
            c_each = min(0.06, 0.35 * dur / max(1, len(cons)))
            for p in phones:
                ph.append(p if p in phone_set else "<SP>"); notes.append(pitch); durs.append(dur); types.append(2)
                if p[-1].isdigit():
                    last_vowel = p; phd.append(round(dur - c_each * len(cons), 4))
                else:
                    phd.append(round(c_each, 4))
        prev_end = r["end"]
    return {"text_gen": ph, "note_gen": notes, "note_dur_gen": durs, "note_type_gen": types, "spk_id": spk, "tech_list": ["0"] * len(ph), "ph_durs": phd}


def main():
    from utils.commons.hparams import set_hparams, hparams
    set_hparams(config="egs/stage2.yaml", exp_name="stage2", print_hparams=False)
    from inference.techsinger import techinfer, self_clone
    import numpy as np
    import torch
    import soundfile as sf

    class Forced(techinfer):
        def preprocess_input(self, inp):
            item = super().preprocess_input(inp); item["ph_durs"] = inp["ph_durs"]; return item

        def forward_model(self, inp):
            s = self.input_to_batch(inp); hop, sr = hparams["hop_size"], hparams["audio_sample_rate"]
            n = int(round(sum(inp["ph_durs"]) * sr / hop)) + 1; m = np.zeros([n], int); t = 0.0
            for i, d in enumerate(inp["ph_durs"]):
                m[int(t * sr / hop + 0.5):int((t + d) * sr / hop + 0.5)] = i + 1; t += d
            mel2ph = torch.LongTensor(m)[None, :].to(self.device)
            two = lambda x: torch.cat((x, torch.ones_like(x) * 2), dim=0)
            with torch.no_grad():
                tech = {k: two(s[k]) for k in ("mix", "falsetto", "breathy", "bubble", "strong", "weak", "pharyngeal", "vibrato", "glissando")}
                out = self.model(self_clone(s["txt_tokens"]), mel2ph=self_clone(mel2ph), spk_id=self_clone(s["spk_id"]), f0=None, uv=None,
                                 note=self_clone(s["notes"]), note_dur=self_clone(s["note_durs"]), note_type=self_clone(s["note_types"]), infer=True, **tech)
                self.model_post(None, True, out, True, cfg_scale=1.0, noise=None)
                wav = self.vocoder.spec2wav(out["mel_out"][0].cpu(), f0=out["f0_denorm_pred"][0].cpu())
            return wav, out["mel_out"][0]

    rows = [r for r in json.load(open(A.score))["rows"] if r["kind"] in ("note", "slur")]
    phone_set = set(json.load(open(TS / "ZHEN_checkpoint_phone_set.json")))
    infer = Forced(hparams); sr = hparams["audio_sample_rate"]
    length = A.length or rows[-1]["end"] + 2
    stem = np.zeros(int(length * sr) + sr, dtype=np.float32)
    for k, p in enumerate(phrases(rows, A.gap)):
        inp = build(p, SPK[A.singer], A.shift, phone_set); inp["gen"] = f"phrase{k:02d}"
        wav, _ = infer.infer_once(inp); wav = np.asarray(wav, dtype=np.float32)
        a = int(p[0]["t"] * sr); b = min(len(stem), a + len(wav)); stem[a:b] += wav[:b - a]
        print(f"phrase {k + 1}: {p[0]['t']:.1f}-{p[-1]['end']:.1f} s, {len(p)} notes, {len(wav) / sr:.1f} s sung", flush=True)
    sf.write(A.out, stem[:int(length * sr)], sr)
    print(f"SUNG (TechSinger {A.singer}, shift {A.shift}): {A.out}")


if __name__ == "__main__":
    main()
