#!/usr/bin/env python3
"""measure.py: automatic singing measures on the voice stem behind each blind rating clip.

    python3 measure.py              # all stages, then build/measures/measures.csv
    python3 measure.py align        # stem-against-mix alignment check only

Each clip = the song's mix from source time `source_start` for 15 s (ratings/key.json). The same 15 s of source time
is cut from the voice stem (stems are on the source clock, time 0 = source 0; `align` checks it). Song projects are
read from $ARRANGE_RUNS. Each stage runs in the Python that has its libraries and writes a JSON to build/measures/:
  acoustic  ($ARRANGE_ANALYSIS_PY: librosa, scipy)                SPR, pitch steadiness, vibrato, pitch error
  asr_hnr   ($ARRANGE_ASR_PY: openai-whisper, parselmouth, jiwer)  WER/CER, HNR
  likeness  ($ARRANGE_VC_PY: resemblyzer)                         speaker cosine against the singer's reference clip
  singmos   ($ARRANGE_SINGMOS_PY: torch, s3prl; SingMOS repo at $ARRANGE_SINGMOS)   predicted singing MOS
Each interpreter defaults to the current Python. Audio is decoded through an ffmpeg pipe; only JSON and CSV are written.
The CSV leaves out the recognised and expected words (they are lyrics); asr_hnr.json keeps them.
"""
import csv, json, os, subprocess, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from stems import SONG_RUN, STEMS, WIN, REF  # noqa: E402

RUNS = Path(os.environ.get("ARRANGE_RUNS", HERE.parents[1] / "runs"))
OUT = HERE / "build/measures"
LEN = 15.0
MP3, WAV = "mp3", "wav"   # audio suffixes
PY = {"acoustic": "ARRANGE_ANALYSIS_PY", "asr_hnr": "ARRANGE_ASR_PY", "likeness": "ARRANGE_VC_PY", "singmos": "ARRANGE_SINGMOS_PY"}


def load(path, start, dur, sr):
    """Mono float32 samples of `path` from `start` for `dur` seconds, resampled to sr (ffmpeg pipe, no temp file)."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(start, 0):.3f}", "-t", f"{dur:.3f}", "-i", str(path),
           "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, check=True, capture_output=True).stdout, dtype=np.float32).copy()


def items():
    """Unique (song, voice) pairs with their stem, plus code list per pair."""
    key = json.load(open(HERE / "ratings/key.json"))
    pairs = {}
    for code, k in key.items():
        s, v = k["song"], k["voice"]
        p = pairs.setdefault((s, v), {"song": s, "voice": v, "codes": [], "start": k["source_start"], "mix": k["mix"]})
        p["codes"].append(code)
    for p in pairs.values():
        stem, fmt, shift = STEMS[p["song"]][p["voice"]]
        p["stem"] = str(Path(SONG_RUN[p["song"]]) / stem)
        p["stem_file"] = RUNS / f"{p['stem']}.{fmt}"
        p["stem_exists"] = p["stem_file"].exists()
        p["shift"] = shift
    return list(pairs.values())


def score_notes(song, t0, t1):
    rows = json.load(open(RUNS / SONG_RUN[song] / "build/studio/sung-score.json"))["rows"]
    return [r for r in rows if r.get("kind") == "note" and r["end"] > t0 and r["t"] < t1]


def score_words(song, t0, t1):
    """Expected words: a word counts if its first note starts inside the window."""
    rows = [r for r in json.load(open(RUNS / SONG_RUN[song] / "build/studio/sung-score.json"))["rows"] if r.get("kind") == "note"]
    words, acc, cur = [], "", None
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    for r in rows:
        w = r.get("word") or r.get("text") or ""
        if cur is None or w != cur[0] or norm(acc) == norm(w):
            cur = (w, r["t"]); acc = ""
            words.append(cur)
        acc += (r.get("text") or "")
    return [w for w, t in words if t0 <= t < t1]


# ---------------------------------------------------------------- stage: acoustic ($ARRANGE_ANALYSIS_PY)
def stage_acoustic():
    import librosa
    from scipy.signal import butter, sosfiltfilt
    SR, HOP = 22050, 256
    FR = SR / HOP
    out = {}
    for it in items():
        if not it["stem_exists"]: continue
        st = it["start"]
        y = load(it["stem_file"], st, LEN, SR)
        f0, vflag, vprob = librosa.pyin(y, fmin=60, fmax=1100, sr=SR, frame_length=2048, hop_length=HOP)
        # pyin decides voicing and the coarse (0.1 semitone grid) pitch; YIN with parabolic interpolation gives
        # the continuous f0 used for cents, kept only where it agrees with pyin within 100 cents (no octave jumps)
        fy = librosa.yin(y, fmin=60, fmax=1100, sr=SR, frame_length=2048, hop_length=HOP)[: len(f0)]
        agree = vflag & (np.abs(1200 * np.log2(fy / np.where(vflag, f0, 1.0))) < 100)
        t = librosa.times_like(f0, sr=SR, hop_length=HOP)
        cents = 1200 * np.log2(np.where(agree, fy, np.nan) / 440.0) + 6900   # MIDI*100
        # --- singing power ratio on voiced frames (Omori 1996: peak of LTAS 2-4 kHz minus peak 0-2 kHz)
        S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP)) ** 2
        n = min(S.shape[1], len(vflag)); S, vf = S[:, :n], vflag[:n]
        freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)
        rms = np.sqrt(S.mean(0)); vf = vf & (rms > 0.05 * rms.max())
        ltas = 10 * np.log10(S[:, vf].mean(1) + 1e-12) if vf.any() else None
        lo, hi = (freqs > 0) & (freqs < 2000), (freqs >= 2000) & (freqs <= 4000)
        spr = float(ltas[hi].max() - ltas[lo].max()) if ltas is not None else None
        e_lo, e_hi = S[lo][:, vf].sum(), S[hi][:, vf].sum()
        spr_energy = float(10 * np.log10(e_hi / e_lo)) if vf.any() else None
        # --- per note
        notes = score_notes(it["song"], st, st + LEN)
        dev_all = [n_["pitch"] for n_ in notes]
        per = []
        for nt in notes:
            a, b = max(nt["t"], st) - st, min(nt["end"], st + LEN) - st
            d = b - a
            trim = max(0.04, 0.15 * d)
            m = (t >= a + trim) & (t <= b - trim)
            c = cents[m]
            if m.sum() < 5 or np.isfinite(c).mean() < 0.6: continue
            per.append({"pitch": nt["pitch"], "dur": d, "c": c})
        shift = it["shift"]
        offs = [np.nanmedian(p["c"]) / 100 - p["pitch"] for p in per]
        offset_st = float(np.median(offs)) if offs else None
        shift_used = shift if shift is not None else (int(round(offset_st)) if offset_st is not None else None)
        steady, vib, err = [], [], []
        for p in per:
            c = p["c"]; idx = np.arange(len(c)); ok = np.isfinite(c)
            c = np.interp(idx, idx[ok], c[ok])
            if shift_used is not None:
                err.append(np.median(c) - 100 * (p["pitch"] + shift_used))
            if p["dur"] >= 0.3:
                sos = butter(2, [4, 8], btype="bandstop", fs=FR, output="sos")
                r = sosfiltfilt(sos, c - c.mean(), padlen=min(len(c) - 1, 15))
                steady.append(float(np.std(r)))
            if p["dur"] >= 0.6:
                x = c - np.polyval(np.polyfit(idx, c, 1), idx)
                N = 4096
                X = np.abs(np.fft.rfft(x * np.hanning(len(x)), N))
                fq = np.fft.rfftfreq(N, 1 / FR)
                band = (fq >= 2) & (fq <= 12)
                k = np.argmax(np.where(band, X, 0))
                ext = 2 * X[k] / np.hanning(len(x)).sum()        # sinusoid amplitude (cents) = half peak-to-peak
                vib.append({"has": bool(4.5 <= fq[k] <= 8 and ext >= 15), "rate": float(fq[k]), "extent": float(ext)})
        err = np.abs(np.array(err))
        vy = [v for v in vib if v["has"]]
        out["|".join([it["song"], it["voice"]])] = {
            "voiced_frac": float(np.mean(vflag)),
            "spr_db": spr, "spr_energy_db": spr_energy,
            "steady_cents": float(np.median(steady)) if steady else None, "steady_n": len(steady),
            "vib_frac": float(len(vy) / len(vib)) if vib else None, "vib_n": len(vib),
            "vib_rate_hz": float(np.median([v["rate"] for v in vy])) if vy else None,
            "vib_extent_cents": float(np.median([v["extent"] for v in vy])) if vy else None,
            "pitch_offset_st": offset_st, "shift_used": shift_used, "shift_inferred": shift is None,
            "pitch_err_cents": float(np.median(err)) if len(err) else None,
            "pitch_within50": float(np.mean(err <= 50)) if len(err) else None, "pitch_n": int(len(err)),
            "notes_in_window": len(notes),
        }
        print("acoustic", it["song"], it["voice"], {k: (round(v, 2) if isinstance(v, float) else v) for k, v in out["|".join([it["song"], it["voice"]])].items()}, flush=True)
    json.dump(out, open(OUT / "acoustic.json", "w"), indent=1)


# ---------------------------------------------------------------- stage: asr + hnr ($ARRANGE_ASR_PY)
def stage_asr_hnr():
    import torch, whisper, jiwer, parselmouth
    dev = "cpu"
    model = whisper.load_model("large-v3-turbo", device=dev, download_root=os.environ.get("ARRANGE_WHISPER_DIR"))
    out = {}
    tr = jiwer.Compose([jiwer.ToLowerCase(), jiwer.RemovePunctuation(), jiwer.RemoveMultipleSpaces(), jiwer.Strip(),
                        jiwer.ReduceToListOfListOfWords()])
    trc = jiwer.Compose([jiwer.ToLowerCase(), jiwer.RemovePunctuation(), jiwer.RemoveWhiteSpace(replace_by_space=False),
                         jiwer.Strip(), jiwer.ReduceToListOfListOfChars()])
    for it in items():
        if not it["stem_exists"]: continue
        st = it["start"]
        y = load(it["stem_file"], st, LEN, 16000)
        lang = "en"
        res = model.transcribe(y, language=lang, temperature=0.0, condition_on_previous_text=False,
                               fp16=(dev == "cuda"), no_speech_threshold=None, logprob_threshold=None)
        hyp = res["text"].strip()
        ref = " ".join(score_words(it["song"], st, st + LEN))
        hyp_ = hyp if hyp else "<empty>"
        wer = jiwer.wer(ref, hyp_, reference_transform=tr, hypothesis_transform=tr)
        cer = jiwer.cer(ref, hyp_, reference_transform=trc, hypothesis_transform=trc)
        # HNR: Praat cross-correlation harmonicity, 10 ms step, 75 Hz floor, 0.1 silence threshold, 1 period/window
        y44 = load(it["stem_file"], st, LEN, 44100).astype(np.float64)
        h = parselmouth.Sound(y44, 44100).to_harmonicity_cc(time_step=0.01, minimum_pitch=75, silence_threshold=0.1, periods_per_window=1.0)
        hv = h.values[0]; hv = hv[hv > -199]
        out["|".join([it["song"], it["voice"]])] = {"asr_lang": lang, "asr_ref": ref, "asr_hyp": hyp, "wer": float(wer), "cer": float(cer),
                                                     "hnr_db": float(np.mean(hv)) if len(hv) else None,
                                                     "hnr_median_db": float(np.median(hv)) if len(hv) else None}
        print("asr", it["song"], it["voice"], round(wer, 3), round(cer, 3), "| ref:", ref, "| hyp:", hyp, flush=True)
    json.dump(out, open(OUT / "asr_hnr.json", "w"), indent=1, ensure_ascii=False)


# ---------------------------------------------------------------- stage: likeness ($ARRANGE_VC_PY)
def ref_audio(name, sr=16000):
    vd = RUNS / "color-purple/voices" / name
    if (vd / f"prompt.{WAV}").exists():
        return load(vd / f"prompt.{WAV}", 0, 600, sr), str((vd / "prompt").relative_to(RUNS))
    c = json.load(open(vd / "prompt-candidates.json"))[0]            # same clip convert_voice.py --clip 1 uses
    return load(vd / f"pre/vocal.{WAV}", c["t"][0], c["t"][1] - c["t"][0], sr), f"{(vd / 'pre/vocal').relative_to(RUNS)}@{c['t'][0]}-{c['t'][1]}"


def stage_likeness():
    from resemblyzer import VoiceEncoder, preprocess_wav
    enc = VoiceEncoder("cpu")
    out, cache = {}, {}
    for it in items():
        if not it["stem_exists"]: continue
        name = REF.get(it["voice"], it["voice"])
        k = "|".join([it["song"], it["voice"]])
        if name is None or not (RUNS / "color-purple/voices" / name).exists():
            out[k] = {"likeness": None, "likeness_ref": None}; continue
        if name not in cache:
            a, src = ref_audio(name)
            cache[name] = (enc.embed_utterance(preprocess_wav(a, source_sr=16000)), src)
        e = enc.embed_utterance(preprocess_wav(load(it["stem_file"], it["start"], LEN, 16000), source_sr=16000))
        r, src = cache[name]
        out[k] = {"likeness": float(np.dot(e, r) / (np.linalg.norm(e) * np.linalg.norm(r))), "likeness_ref": src}
        print("likeness", k, round(out[k]["likeness"], 3), flush=True)
    json.dump(out, open(OUT / "likeness.json", "w"), indent=1)


# ---------------------------------------------------------------- stage: SingMOS ($ARRANGE_SINGMOS_PY)
def stage_singmos():
    import torch
    if os.environ.get("ARRANGE_SINGMOS_HUB"):
        torch.hub.set_dir(os.environ["ARRANGE_SINGMOS_HUB"])
    model = torch.hub.load(os.environ["ARRANGE_SINGMOS"], "singmos_pro", source="local", trust_repo=True).to("cpu").eval()
    out = {}
    for it in items():
        if not it["stem_exists"]: continue
        y = torch.from_numpy(load(it["stem_file"], it["start"], LEN, 16000)).unsqueeze(0)
        with torch.no_grad():
            s = model(y, torch.tensor([y.shape[1]]))
        out["|".join([it["song"], it["voice"]])] = {"singmos_pro": float(s.reshape(-1)[0])}
        print("singmos", it["song"], it["voice"], out["|".join([it["song"], it["voice"]])], flush=True)
    json.dump(out, open(OUT / "singmos.json", "w"), indent=1)


# ---------------------------------------------------------------- alignment check
def stage_align():
    SR = 8000
    out = {}
    for it in items():
        if not it["stem_exists"]: continue
        st, w = it["start"], WIN[it["song"]]
        mix = load(RUNS / f"{it['mix']}.{MP3}", st - w, LEN, SR)
        lo = max(0.0, st - 25)
        y = load(it["stem_file"], lo, 55, SR)
        n = 1 << int(np.ceil(np.log2(len(y) + len(mix))))
        c = np.fft.irfft(np.fft.rfft(y, n) * np.conj(np.fft.rfft(mix, n)), n)[: len(y) - len(mix) + 1]
        cs = np.concatenate([[0], np.cumsum(y.astype(np.float64) ** 2)])
        e = np.sqrt(np.maximum(cs[len(mix):] - cs[:-len(mix)], 0))       # stem energy under each lag
        cn = np.where(e > 0.2 * e.max(), c / (e * np.linalg.norm(mix) + 1e-9), 0)
        i = int(np.argmax(np.abs(cn)))
        out["|".join([it["song"], it["voice"]])] = {"lag_s": round(lo + i / SR - st, 3), "corr": round(float(cn[i]), 3)}
        print("align", it["song"], it["voice"], out["|".join([it["song"], it["voice"]])], flush=True)
    json.dump(out, open(OUT / "align.json", "w"), indent=1)


def merge():
    parts = {}
    for name in ["align", "acoustic", "asr_hnr", "likeness", "singmos"]:
        p = OUT / f"{name}.json"
        parts[name] = json.load(open(p)) if p.exists() else {}
    cols = ["code", "song", "voice", "repeat_of", "stem", "stem_found", "align_lag_s", "align_corr",
            "spr_db", "spr_energy_db", "steady_cents", "steady_n", "vib_frac", "vib_n", "vib_rate_hz", "vib_extent_cents",
            "pitch_err_cents", "pitch_within50", "pitch_n", "pitch_offset_st", "shift_used", "shift_inferred",
            "hnr_db", "hnr_median_db", "wer", "cer", "asr_lang", "likeness", "likeness_ref", "singmos_pro", "voiced_frac"]
    rows = []
    for it in items():
        k = "|".join([it["song"], it["voice"]])
        base = {"song": it["song"], "voice": it["voice"], "stem": it["stem"], "stem_found": it["stem_exists"]}
        a = parts["align"].get(k, {}); base.update({"align_lag_s": a.get("lag_s"), "align_corr": a.get("corr")})
        for name in ["acoustic", "asr_hnr", "likeness", "singmos"]:
            base.update(parts[name].get(k, {}))
        for i, code in enumerate(it["codes"]):
            r = dict(base, code=code, repeat_of=(it["codes"][0] if i else ""))
            rows.append({c: (round(r[c], 4) if isinstance(r.get(c), float) else r.get(c)) for c in cols})
    rows.sort(key=lambda r: r["code"])
    with open(OUT / "measures.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print("wrote", OUT / "measures.csv", len(rows), "rows (compare with measures/measures.csv)")


STAGES = {"align": stage_align, "acoustic": stage_acoustic, "asr_hnr": stage_asr_hnr, "likeness": stage_likeness, "singmos": stage_singmos}

if __name__ == "__main__":
    want = sys.argv[1:] or ["align", "acoustic", "asr_hnr", "likeness", "singmos", "merge"]
    OUT.mkdir(parents=True, exist_ok=True)
    for s in want:
        if s == "merge": merge(); continue
        if os.environ.get("MEASURE_IN_VENV") == s:
            STAGES[s](); continue
        py = os.environ.get(PY.get(s, "ARRANGE_ANALYSIS_PY"), sys.executable)
        # every stage runs on the CPU
        r = subprocess.run([py, __file__, s], env=dict(os.environ, MEASURE_IN_VENV=s, PYTHONWARNINGS="ignore", CUDA_VISIBLE_DEVICES=""))
        if r.returncode: print(f"stage {s} failed (exit {r.returncode})")
