#!/usr/bin/env python3
"""run_center.py: can a language model pick the key for a copied voice, and what does ARRANGE's measurement add?

    python3 run_center.py --model claude-sonnet-5-5 --draws 3 --out results-new
    python3 run_center.py --model qwen3.5-27b-fp8 --base-url http://localhost:8011/v1 --out results-new
    python3 run_center.py --table                     # TABLE.md from results/

Cases: the 8 song x voice pairs the composer had keyed by ear on the canvas (GOLD). Shift = semitones the voice sings
relative to the written melody (the convention of skills/arrange-lyrics/scripts/center.py). Conditions, with the same
question and answer format in each:
  name      the singer's name and the song's melody range only (the model's own knowledge of the singer)
  numbers   + center.py's measurement of the singer's whole separated recording (10/25/50/75/90th percentile notes)
  anon      the same numbers with the name replaced by "Voice A" (reasoning from the measurement alone)
  image     anon, but the measurement is given as a picture (histogram of the singer's notes over the song's notes)
None of these models hears audio here; the "listening" is reading a pitch measurement, as numbers or as a picture.

Prompts: the text conditions are read from prompts.jsonl (the exact text sent in the paper's runs). The image condition
draws its picture from the song projects and the singers' pitch tracks, which are not distributed: point ARRANGE_RUNS
at the projects (voices in $ARRANGE_RUNS/color-purple/voices, fits in $ARRANGE_RUNS/<song>/plan/fit/fit.json), and the
text conditions are then rebuilt from them too.
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
K = HERE.parent; REPO = K.parents[1]
RUNS = Path(os.environ["ARRANGE_RUNS"]) if os.environ.get("ARRANGE_RUNS") else None
VOICES = RUNS / "color-purple/voices" if RUNS else None
NAMES = {"buble": "Michael Bublé", "jackson": "Michael Jackson", "clarkson": "Kelly Clarkson", "bolton": "Michael Bolton",
         "ariana": "Ariana Grande", "wonder": "Stevie Wonder", "groban": "Josh Groban", "adams": "Bryan Adams"}
SONGS = {"attya": ("All the Things You Are", "all-the-things-cohen"), "someday": ("Someday My Prince Will Come", "someday-my-prince")}
GOLD = [("attya", "buble", -8), ("attya", "jackson", -4), ("attya", "clarkson", 2), ("attya", "bolton", -4), ("attya", "ariana", 2),
        ("attya", "wonder", 2), ("someday", "clarkson", 1), ("someday", "ariana", -2)]
NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
IMG = K / "build/center-img"
FROZEN = {(r["case"], r["cond"]): r["text"] for r in map(json.loads, open(HERE / "prompts.jsonl"))}
SYSTEM = "You are an experienced vocal arranger."


def center():
    sys.path.insert(0, str(REPO / "skills/arrange-lyrics/scripts"))
    import center as C  # noqa: E402
    return C


def nn(m):
    m = int(round(m)); return f"{NOTE[m % 12]}{m // 12 - 1}"


def song_notes(s):   # the same reading as center.song_profile: note rows, weighted by duration
    C = center(); rows = [r for r in json.load(open(RUNS / SONGS[s][1] / "plan/fit/fit.json"))["rows"] if r.get("kind") == "note"]
    return np.repeat([r["pitch"] for r in rows], [max(1, int(round((r["end"] - r["t"]) * C.FPS))) for r in rows])


def describe_song(s):
    v = song_notes(s); q = np.percentile(v, [0, 10, 50, 90, 100])
    return SONGS[s][0], f"written melody: lowest {nn(q[0])}, 10th percentile {nn(q[1])}, middle (time-weighted median) {nn(q[2])}, 90th percentile {nn(q[3])}, highest {nn(q[4])}", v


def voice_notes(vd):
    C = center(); f0 = vd / "pre/vocal_f0.npy"
    return C.midi(np.load(f0)) if f0.exists() else C.clip_notes(vd / "prompt.json")


def describe_voice(vd):
    v = voice_notes(vd); q = np.percentile(v, [10, 25, 50, 75, 90])
    src = "the singer's whole separated recording" if (vd / "pre/vocal_f0.npy").exists() else "a 10-second reference clip only"
    return f"measured from {src} ({len(v) / 50:.0f} s sung): 10th percentile {nn(q[0])}, 25th {nn(q[1])}, median {nn(q[2])}, 75th {nn(q[3])}, 90th {nn(q[4])}", v


def picture(song_v, voice_v, path):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    lo, hi = int(min(song_v.min(), np.percentile(voice_v, 1))) - 3, int(max(song_v.max(), np.percentile(voice_v, 99))) + 3
    bins = np.arange(lo, hi + 1) - 0.5
    fig, ax = plt.subplots(figsize=(9, 4), dpi=110)
    ax.hist(np.clip(voice_v, lo, hi), bins=bins, density=True, alpha=0.6, color="#3b7dd8", label="Voice A: notes sung in their recording")
    ax.hist(song_v, bins=bins, density=True, alpha=0.6, color="#e07b39", label="the song's written melody")
    ticks = [m for m in range(lo, hi + 1) if m % 12 in (0, 4, 7)]
    ax.set_xticks(ticks); ax.set_xticklabels([nn(m) for m in ticks], fontsize=8)
    ax.set_xlabel("pitch (note name, C4 = middle C)"); ax.set_ylabel("share of time"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


QUESTION = """A composer wants this singer's cloned voice to sing their song. A voice clone sounds like the singer only where the
singer actually sings, and strains or sounds wrong when pushed outside that range. Choose the transposition: the number of
semitones (an integer, negative = lower) to move the written melody so the voice sings it in its most comfortable,
best-sounding place. Answer ONLY with JSON: {"shift": <integer>, "why": "<one sentence>"}"""


def prompt(cond, s, voice):
    if RUNS is None:
        if cond == "image":
            raise SystemExit("the image condition needs ARRANGE_RUNS (song projects and voice pitch tracks)")
        return FROZEN[(f"{s}/{voice}", cond)], None
    title, sdesc, sv = describe_song(s)
    vdesc, vv = describe_voice(VOICES / voice)
    who = NAMES[voice] if cond in ("name", "numbers") else "Voice A"
    parts = [f"SONG: {title}; {sdesc}.", f"SINGER: {who}."]
    if cond in ("numbers", "anon"):
        parts.append(f"The singer's range, {vdesc}.")
    img = None
    if cond == "image":
        IMG.mkdir(parents=True, exist_ok=True); img = IMG / f"{s}-{voice}.png"; picture(sv, vv, img)
        parts.append("The picture shows how much time Voice A spends on each note in their own recording (blue) over the notes of the song's written melody (orange).")
    return "\n".join(parts) + "\n\n" + QUESTION, img


def call_claude(text, model, img):
    """One completion from the Claude Code CLI, run in an empty temporary folder (no project instructions or memory)."""
    cmd = ["claude", "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--system-prompt", SYSTEM]
    with tempfile.TemporaryDirectory(prefix="center-") as tmp:
        if img:
            local = Path(tmp) / img.name; shutil.copy(img, local)
            text = f"First read the image file {local} (it is the picture referred to below).\n\n" + text
            cmd += ["--allowedTools", "Read"]
        else:
            cmd += ["--disallowedTools", "Bash", "Read", "Write", "Edit", "Agent", "WebFetch", "WebSearch", "Glob", "Grep"]
        r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=600, cwd=tmp)
    j = json.loads(r.stdout); return j.get("result", ""), j.get("total_cost_usd") or 0


def call_openai(text, model, img, base):
    import urllib.request
    content = [{"type": "text", "text": text}]
    if img:
        content.insert(0, {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(img.read_bytes()).decode()}})
    body = {"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}], "max_tokens": 24000}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    j = json.loads(urllib.request.urlopen(req, timeout=1200).read())
    return re.sub(r"<think>.*?</think>", "", j["choices"][0]["message"].get("content") or "", flags=re.S), 0.0


def parse(t):
    m = re.search(r"\{.*\}", t, re.S)
    try:
        return int(round(float(json.loads(m.group(0))["shift"])))
    except Exception:
        m2 = re.search(r'"shift"\s*:\s*(-?\d+)', t); return int(m2.group(1)) if m2 else None


def table():
    gold = {f"{s}/{v}": g for s, v, g in GOLD}
    rs = json.load(open(K / "data/profiles.json"))["rules"]
    lines = [f"# Key choice: the model alone and with ARRANGE's voice measurement (gold = the composer's {len(gold)} sighted keys on the canvas)", "",
             "| who | condition | mean abs error (semitones) | within ±2 | octave errors (≥ 9 off) | unparsed |", "|---|---|---|---|---|---|"]
    for rule in ("topnote", "top", "median", "clip"):
        e = [abs(rs[k][rule] - g) for k, g in gold.items()]
        lines.append(f"| center.py (no model) | rule {rule} | {np.mean(e):.1f} | {sum(x <= 2 for x in e)}/{len(e)} | {sum(x >= 9 for x in e)} | 0 |")
    for f in sorted((HERE / "results").glob("*.json")):
        res = json.load(open(f))
        for cond in ("name", "numbers", "anon", "image"):
            rows = [r for r in res["rows"] if r["cond"] == cond]
            if not rows:
                continue
            e = [abs(r["shift"] - gold[r["case"]]) for r in rows if r["shift"] is not None]
            lines.append(f"| {res['model']} | {cond} | {np.mean(e):.1f} | {sum(x <= 2 for x in e)}/{len(rows)} | {sum(x >= 9 for x in e)} | {sum(r['shift'] is None for r in rows)} |")
    (HERE / "TABLE.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--draws", type=int, default=3); ap.add_argument("--base-url")
    ap.add_argument("--conds", nargs="*", default=["name", "numbers", "anon", "image"]); ap.add_argument("--table", action="store_true")
    ap.add_argument("--out", default="results-new", help="folder (under llm/) for the new results; resumes from a file already there")
    a = ap.parse_args()
    if a.table:
        return table()
    out = HERE / a.out / f"{a.model}.json"; out.parent.mkdir(exist_ok=True)
    res = json.load(open(out)) if out.exists() else {"model": a.model, "rows": []}
    done = {(r["case"], r["cond"], r["draw"]) for r in res["rows"]}
    for s, v, g in GOLD:
        for cond in a.conds:
            for k in range(1, a.draws + 1):
                if (f"{s}/{v}", cond, k) in done:
                    continue
                text, img = prompt(cond, s, v); t = time.time()
                try:
                    ans, cost = call_openai(text, a.model, img, a.base_url) if a.base_url else call_claude(text, a.model, img)
                except Exception as e:
                    ans, cost = f"ERROR {e}", 0
                sh = parse(ans)
                res["rows"].append({"case": f"{s}/{v}", "cond": cond, "draw": k, "shift": sh, "gold": g, "answer": ans[:600], "cost": cost, "elapsed": round(time.time() - t, 1)})
                print(f"{a.model} {s}/{v} {cond} d{k}: {sh} (ear {g})", flush=True)
                out.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
