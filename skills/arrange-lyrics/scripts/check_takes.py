#!/usr/bin/env python3
"""check_takes.py — find the faults in several takes of the same sung line, so the composer only listens to clean ones
(/arrange-lyrics; a Python with openai-whisper + librosa; CPU is fine).

    python check_takes.py --score build/studio/sung-score.json --take mine-a:-9:voice/a.mp3 --take mine-b:-9:voice/b.mp3 \
        [--window 25.5 102.8] [--json takes.json]

SoulX samples: every render of the same score is a new take unless the seed is fixed (sing.py --takes N, --seed),
and takes differ a lot: a second take of the same voice can drop one note from mostly in tune to half in tune,
and a word one take swallows can be there in the next. So render a few takes and check each:

  words missed  Whisper (large-v3-turbo by default; temperature 0, no lyric prompt) on each sung line; the line's words are matched
                in order and the ones it does not hear are listed. A swallowed syllable shows up here.
  in tune       per note, the share of its frames within 50 cents of score + shift (pyin), averaged over the notes.
                A note sung late or slid into shows up as a low share; 'worst' lists the five lowest notes.

These are fault checks, not quality: a take can pass both and still sound worse (pitch is not quality, see
references/keys.md). Ranking: fewest words missed, then most in tune. The composer listens to
the top takes and decides.
"""
import argparse, difflib, json, os, re, subprocess, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent)); import arrange_config  # noqa: E402


def load_pcm(path, t0, dur, sr):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(max(0, t0)), "-t", str(dur), "-i", path, "-ac", "1", "-ar", str(sr),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768


def lines_of(rows, gap=0.8):
    out, cur = [], [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if b["t"] - a["end"] > gap: out.append(cur); cur = []
        cur.append(b)
    return out + [cur]


def norm(s):
    return re.sub(r"[^a-z']", "", s.lower().replace("evry", "every"))


def words_of(line):   # one entry per word: a word starts on the note whose syllable begins it
    return [norm(r["word"]) for r in line if norm(r["text"]) and norm(r["word"]).startswith(norm(r["text"]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True); ap.add_argument("--take", action="append", required=True, help="name:shift:stem.mp3")
    ap.add_argument("--window", type=float, nargs=2); ap.add_argument("--language", default="en"); ap.add_argument("--json"); ap.add_argument("--device", default="cpu", help="cpu, or cuda when the GPU is free")
    a = ap.parse_args()
    if a.device == "cpu": os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
    import librosa, whisper
    rows = [r for r in json.load(open(a.score))["rows"] if r.get("kind") == "note"]
    if a.window: rows = [r for r in rows if a.window[0] <= r["t"] < a.window[1]]
    lines = lines_of(rows)
    cfg = arrange_config.load()   # whisper.model / whisper.cache (ARRANGE_WHISPER_MODEL / ARRANGE_WHISPER_CACHE); no cache = Whisper's own default
    model = whisper.load_model(arrange_config.get(cfg, "whisper.model", "large-v3-turbo"), device=a.device, download_root=arrange_config.get(cfg, "whisper.cache"))
    res = []
    for spec in a.take:
        name, shift, path = spec.split(":", 2); shift = int(shift)
        missed = []
        for L in lines:
            t0, t1 = L[0]["t"] - 0.25, L[-1]["end"] + 0.3
            txt = model.transcribe(load_pcm(path, t0, t1 - t0, 16000), language=a.language, temperature=0, fp16=a.device != "cpu")["text"]
            ref, hyp = words_of(L), [norm(w) for w in txt.split() if norm(w)]
            got = {i for b in difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False).get_matching_blocks() for i in range(b.a, b.a + b.size)}
            missed += [f"{ref[i]} ({L[0]['t']:.0f} s)" for i in range(len(ref)) if i not in got]
        T0, T1 = rows[0]["t"] - 0.2, rows[-1]["end"] + 0.2
        y = load_pcm(path, T0, T1 - T0, 22050)
        f0, _, _ = librosa.pyin(y, fmin=70, fmax=1100, sr=22050, frame_length=1024, hop_length=220)
        t = T0 + np.arange(len(f0)) * 220 / 22050; m = 69 + 12 * np.log2(f0 / 440)
        per = []
        for r in rows:
            c = 100 * (m[(t >= r["t"]) & (t < r["end"])] - r["pitch"] - shift)
            per.append((float(np.mean(np.abs(np.nan_to_num(c, nan=999)) < 50)) if len(c) else 0.0, r))
        worst = sorted(per, key=lambda x: x[0])[:5]
        res.append({"take": name, "stem": path, "shift": shift, "words_missed": missed, "in_tune": round(float(np.mean([p for p, _ in per])), 3),
                    "worst_notes": [f"{r['text']} ({r['t']:.1f} s) {p:.2f}" for p, r in worst]})
        print(f"{name}: {len(missed)} word(s) missed, {res[-1]['in_tune']:.2f} in tune", flush=True)
    res.sort(key=lambda x: (len(x["words_missed"]), -x["in_tune"]))
    print("\nranked (fewest words missed, then most in tune):")
    for x in res:
        print(f"  {x['take']:22s} missed {len(x['words_missed'])}: {', '.join(x['words_missed']) or '-':40s} in tune {x['in_tune']:.2f}")
    if a.json: json.dump(res, open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
