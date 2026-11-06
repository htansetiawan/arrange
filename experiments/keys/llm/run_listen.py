#!/usr/bin/env python3
#!/usr/bin/env python3
"""run_listen.py: can an open audio model hear where a voice sits? (served by vLLM, OpenAI-compatible, audio input)

    python3 run_listen.py --model gemma-4-e4b-it --base-url http://localhost:8011/v1 --draws 3 --out listen-results-new
    python3 run_listen.py --table                     # LISTEN-TABLE.md from listen-results/

Clips (not distributed; rebuilt from the separated vocals under $ARRANGE_RUNS/color-purple/voices into ../build/listen-clips):
for each voice, the 30 s of its separated whole recording (pre/vocal) with the most sung frames, 16 kHz mono;
plus two controls, synthetic sung-like tones (vibrato sine with harmonics) with a known centre (A3 and E4).
Q1 perceive: the low / centre / high note the singer sings in the clip, as note names. Truth = the same clip's measured
     pitch track (pre/vocal_f0.npy, the frames inside the clip): 10th percentile, median, 90th percentile. Stored in
listen-truth.json with each clip's start time.
Q2 key: the song's written range (as in run_center.py) + the clip; the shift. Gold = the composer's 8 sighted keys.
Q1 also asks about Groban's clip (his reference clip), whose sighted key is on a song that is not distributed.
Errors in semitones; octave confusions are counted separately (|error| >= 9).
"""
import argparse, base64, io, json, os, re, subprocess, sys, wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_center as RC  # noqa: E402

CLIPS = HERE.parent / "build/listen-clips"; TRUTH = HERE / "listen-truth.json"; SR = 16000; LEN = 30
WAV = "wav"   # audio suffix
NOTE_RE = re.compile(r"^([A-Ga-g])([#b♯♭]?)(-?\d)$")


def note_to_midi(s):
    m = NOTE_RE.match(str(s).strip().replace("♯", "#").replace("♭", "b"))
    if not m:
        return None
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1).upper()]
    return base + {"#": 1, "b": -1, "": 0}[m.group(2)] + 12 * (int(m.group(3)) + 1)


def make_clips():
    CLIPS.mkdir(exist_ok=True); truth = {}
    for v in sorted({v for _, v, _ in RC.GOLD} | {"groban"}):
        vd = RC.VOICES / v; f0p = vd / "pre/vocal_f0.npy"
        if not f0p.exists():   # no whole recording separated (groban): use the reference clip and its notes
            src, f0 = vd / f"prompt.{WAV}", None
            start = 0.0
        else:
            f0 = np.load(f0p); voiced = (f0 > 0).astype(float); w = LEN * 50
            csum = np.convolve(voiced, np.ones(w), "valid"); i = int(np.argmax(csum)); start = i / 50
            src = vd / f"pre/vocal.{WAV}"
        out = CLIPS / f"{v}.{WAV}"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", str(LEN), "-i", str(src), "-ac", "1", "-ar", str(SR),
                        "-af", "loudnorm=I=-20", str(out)], check=True)
        if f0 is not None:
            seg = f0[int(start * 50): int(start * 50) + LEN * 50]; mid = RC.center().midi(seg)
        else:
            mid = RC.center().clip_notes(vd / "prompt.json")
        q = np.percentile(mid, [10, 50, 90]); truth[v] = {"low": float(q[0]), "centre": float(q[1]), "high": float(q[2]), "start": start}
    for name, centre in (("control-A3", 57), ("control-E4", 64)):   # a slow line around the centre: centre, +-2, +-4 semitones
        notes = [centre, centre + 2, centre - 2, centre, centre + 4, centre - 4, centre, centre + 2, centre]
        t = np.arange(int(SR * 3.0)) / SR; sig = []
        for n in notes:
            f = 440 * 2 ** ((n - 69) / 12) * (1 + 0.006 * np.sin(2 * np.pi * 5.5 * t))
            ph = 2 * np.pi * np.cumsum(f) / SR
            tone = sum(a * np.sin(k * ph) for k, a in ((1, 1), (2, .5), (3, .3), (4, .15)))
            env = np.minimum(1, np.minimum(t / .08, (t[-1] - t) / .15))
            sig.append(tone * env)
        x = np.concatenate(sig)[: SR * LEN]; x = (x / np.abs(x).max() * 0.5 * 32767).astype(np.int16)
        with wave.open(str(CLIPS / f"{name}.{WAV}"), "wb") as wv:
            wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR); wv.writeframes(x.tobytes())
        q = np.percentile(np.repeat(notes, 1), [10, 50, 90]); truth[name] = {"low": float(min(notes)), "centre": float(centre), "high": float(max(notes)), "synthetic": True}
    json.dump(truth, open(CLIPS / "truth.json", "w"), indent=1)   # compare with the stored listen-truth.json
    return truth


Q1 = """Listen to this recording of a singer (the voice alone). Which notes do they sing? Give the low end of what they
comfortably sing, the note they sit on most (their centre), and the high end, as note names with octave numbers
(C4 = middle C, A4 = 440 Hz). Answer ONLY with JSON: {"low": "<note>", "centre": "<note>", "high": "<note>"}"""


def call(base, model, text, wav):
    import urllib.request
    b64 = base64.b64encode(Path(wav).read_bytes()).decode()
    content = [{"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64," + b64}}, {"type": "text", "text": text}]
    body = {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": 2000, "temperature": 0.7}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return re.sub(r"<think>.*?</think>", "", j["choices"][0]["message"].get("content") or "", flags=re.S)


def jparse(t):
    m = re.search(r"\{.*?\}", t, re.S)
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def table():
    truth = json.load(open(TRUTH)); gold = {f"{s}/{v}": g for s, v, g in RC.GOLD}
    lines = ["# Can an open audio model hear where a voice sits?", "",
             "| model | perceive: centre abs err (semitones) | low / high abs err | octave confusions (centre) | controls centre err | key: abs err vs ear | key within ±2 | unparsed |",
             "|---|---|---|---|---|---|---|---|"]
    for f in sorted((HERE / "listen-results").glob("*.json")):
        res = json.load(open(f)); P = [r for r in res["rows"] if r["q"] == "perceive"]; K = [r for r in res["rows"] if r["q"] == "key"]
        def err(r, k):
            m = note_to_midi(r["ans"].get(k)); return None if m is None else m - truth[r["clip"]][k]
        ce = [err(r, "centre") for r in P if not r["clip"].startswith("control")]; ce = [e for e in ce if e is not None]
        lh = [abs(e) for r in P if not r["clip"].startswith("control") for e in (err(r, "low"), err(r, "high")) if e is not None]
        cc = [abs(e) for r in P if r["clip"].startswith("control") for e in [err(r, "centre")] if e is not None]
        ke = [abs(r["shift"] - gold[r["case"]]) for r in K if r["shift"] is not None]
        unp = sum(1 for r in P if note_to_midi(r["ans"].get("centre")) is None) + sum(1 for r in K if r["shift"] is None)
        lines.append(f"| {res['model']} | {np.mean(np.abs(ce)):.1f} | {np.mean(lh):.1f} | {sum(abs(e) >= 9 for e in ce)}/{len(ce)} | "
                     f"{np.mean(cc) if cc else float('nan'):.1f} | {np.mean(ke) if ke else float('nan'):.1f} | {sum(e <= 2 for e in ke)}/{len(K)} | {unp} |")
    (HERE / "LISTEN-TABLE.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--base-url"); ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--table", action="store_true"); ap.add_argument("--clips-only", action="store_true")
    ap.add_argument("--out", default="listen-results-new", help="folder (under llm/) for the new results")
    a = ap.parse_args()
    if a.table:
        return table()
    truth = json.load(open(CLIPS / "truth.json")) if (CLIPS / "truth.json").exists() else make_clips()
    if a.clips_only:
        return print(json.dumps({k: {x: RC.nn(y) if isinstance(y, float) and x in ("low", "centre", "high") else y for x, y in v.items()} for k, v in truth.items()}, indent=1))
    out = HERE / a.out / f"{a.model}.json"; out.parent.mkdir(exist_ok=True)
    res = json.load(open(out)) if out.exists() else {"model": a.model, "rows": []}
    done = {(r["q"], r.get("clip") or r.get("case"), r["draw"]) for r in res["rows"]}
    for k in range(1, a.draws + 1):
        for clip in truth:
            if ("perceive", clip, k) in done:
                continue
            try:
                t = call(a.base_url, a.model, Q1, CLIPS / f"{clip}.{WAV}")
            except Exception as e:
                t = f"ERROR {e}"
            res["rows"].append({"q": "perceive", "clip": clip, "draw": k, "ans": jparse(t), "raw": t[:500]})
            print(a.model, "perceive", clip, k, jparse(t), flush=True); out.write_text(json.dumps(res, indent=1, ensure_ascii=False))
        for s, v, g in RC.GOLD:
            if ("key", f"{s}/{v}", k) in done:
                continue
            title, sdesc, _ = RC.describe_song(s)
            text = (f"SONG: {title}; {sdesc}.\nSINGER: the voice in this recording (listen to it).\n\n" + RC.QUESTION)
            try:
                t = call(a.base_url, a.model, text, CLIPS / f"{v}.{WAV}")
            except Exception as e:
                t = f"ERROR {e}"
            res["rows"].append({"q": "key", "case": f"{s}/{v}", "draw": k, "shift": RC.parse(t), "gold": g, "raw": t[:500]})
            print(a.model, "key", s, v, k, RC.parse(t), "ear", g, flush=True); out.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
