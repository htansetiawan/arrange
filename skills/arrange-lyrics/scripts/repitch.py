#!/usr/bin/env python3
"""repitch.py — keep the beats, change the pitches: the composer dictates a phrase's notes by name (/arrange-lyrics technique; analysis python).

    python repitch.py --score jobs/verse1/score.json --analysis piano-analysis.json --from-word Quiet --pitches "E4 D4 C4 C4 D4 E4 F4" -o jobs/verse1/ [--title ...]

The sung notes from the first row whose word matches --from-word take the
given pitches in order (held notes follow the note they hold); timing is
untouched. The score, lyric-fit, notation picture and ABC are rewritten and
the change is recorded on each row ("pitch set by the composer").
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
import notate  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def midi_of(name):
    m = re.fullmatch(r"([A-G])([#b]?)(-?\d)", name.strip())
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    return 12 * (int(m.group(3)) + 1) + base + {"#": 1, "b": -1, "": 0}[m.group(2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--from-word", required=True); ap.add_argument("--pitches", required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--title", default="Verse 1, pitches as the composer set them")
    a = ap.parse_args()
    sc = json.load(open(a.score)); rows = sc["rows"]; pitches = [midi_of(p) for p in a.pitches.split()]
    start = next(i for i, r in enumerate(rows) if r["kind"] == "note" and r.get("word", "").lower().startswith(a.from_word.lower()))
    changed, k, i = [], 0, start
    while i < len(rows) and k < len(pitches):
        r = rows[i]
        if r["kind"] == "note":
            old = r["pitch"]; r["pitch"] = pitches[k]; r["placed"] = "pitch set by the composer, timing from the piano's line"; k += 1
            changed.append(f"{r['text']}: {NAMES[old % 12]}{old // 12 - 1} -> {NAMES[r['pitch'] % 12]}{r['pitch'] // 12 - 1}")
        elif r["kind"] == "slur":
            r["pitch"] = rows[i - 1]["pitch"]
        i += 1
    while i < len(rows) and rows[i]["kind"] == "slur":
        rows[i]["pitch"] = rows[i - 1]["pitch"]; i += 1
    if k < len(pitches):
        changed.append(f"{len(pitches) - k} pitch(es) left over: the phrase had only {k} sung notes from '{a.from_word}'")
    sc.setdefault("report", []).append(f"composer set pitches from '{a.from_word}': " + "; ".join(changed))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(sc, open(out / "score.json", "w"), indent=1, ensure_ascii=False)
    clk = Clock(json.load(open(a.analysis)))
    q = notate.quantise([dict(r) for r in rows if r["kind"] != "unsung"], clk, 4)
    notate.write_abc(q, out / "fit.abc", a.title); notate.write_musicxml(q, out / "fit.musicxml", a.title, 4); notate.engrave(out / "fit.musicxml", out / "fit.svg", out / "fit.png")
    for c in changed:
        print("REPITCH:", c)


if __name__ == "__main__":
    main()
