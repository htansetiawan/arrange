#!/usr/bin/env python3
"""dictate.py — the composer dictates a line: where it starts, the pitches, the words; even notes on the beat grid (/arrange-lyrics technique; analysis python).

    line format:  <start s, or -N for N beats after the previous line> | <notes in shorthand> | <words>
    shorthand:    C4 one beat of the composer's feel, C4/ half, C4// quarter, C4*2 two beats, z a beat of rest, z/ half
    python dictate.py --score jobs/verse1/score.json --analysis piano-analysis.json --script lines.dictated -o jobs/verse1/ [--step 0.5] [--title ...]

The script file has one line per dictated line:
    27.0 | E4 D4 C4 C4 D4 E4 F4 | Quiet lanterns light the hill
Start is seconds in the recording (snapped to the map's grid), then the
pitches, then the words. Each syllable gets one note of `--step` beats of the
map (0.5 = half a slow beat, the composer's quarter), legato. The syllable
count must equal the pitch count, or the line is reported and left alone. The
dictated line replaces the same words where they already sit in the score;
other lines are untouched. Notation and ABC are redrawn.
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
import notate  # noqa: E402
from lay import syllabify_text  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def midi_of(name):
    m = re.fullmatch(r"([A-G])([#b]?)(-?\d)", name.strip())
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    return 12 * (int(m.group(3)) + 1) + base + {"#": 1, "b": -1, "": 0}[m.group(2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--script", required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--step", type=float, default=0.5); ap.add_argument("--title", default="Verse 1, lines as the composer dictated them")
    a = ap.parse_args()
    sc = json.load(open(a.score)); rows = [r for r in sc["rows"] if r["kind"] != "unsung"]; clk = Clock(json.load(open(a.analysis)))
    report = []; prev_end_o = 0.0
    for raw in Path(a.script).read_text().splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        start_s, pitches, words = [x.strip() for x in raw.split("|")]
        start_s = float(start_s)
        # tokens in the composer's shorthand: C4 = one beat of the composer's feel (a.step of the map), C4/ half, C4// quarter, C4*2 two beats, z / z/ rests
        notes_, pos = [], 0.0
        for tok in pitches.replace("|", " ").split():
            tok = re.sub(r",(\d+(?:\.\d+)?)$", r"*\1", tok)
            tok = re.sub(r"^z(\d+(?:\.\d+)?)", r"z*\1", tok)   # z6 = six beats of rest (a digit after z is a length, not an octave)
            tok = re.sub(r"^z\*(\d+(?:\.\d+)?)(/+)$", r"z\2*\1", tok)
            m = re.fullmatch(r"([zA-G][#b]?-?\d?)(/*)(?:\*(\d+(?:\.\d+)?))?", tok)
            if not m:
                raise SystemExit(f"cannot read '{tok}' in: {raw}")
            ln = a.step * (0.5 ** len(m.group(2))) * (float(m.group(3)) if m.group(3) else 1.0)
            if m.group(1).startswith("z"):
                pos += ln; continue
            notes_.append((pos, ln, midi_of(m.group(1)))); pos += ln
        pitches = [n[2] for n in notes_]
        syl = [(s, w) for w in re.findall(r"[A-Za-z']+", words) for s in syllabify_text(w)]
        if len(syl) > len(pitches):
            report.append(f"'{words}': {len(syl)} syllables but {len(pitches)} pitches; left as it was"); continue
        extra = len(pitches) - len(syl)
        if extra:
            report.append(f"'{words}': {len(pitches)} notes for {len(syl)} syllables; the last {extra} note(s) are placed but unsung until you say which words they carry")
            syl = syl + [("", None)] * extra
        if start_s < 0:   # "-N": N beats of the composer's feel after the end of the previous dictated line
            o = prev_end_o + (-start_s) * a.step
        else:
            bar, beat = clk.at(start_s); o = round(clk._ordinal(bar, beat) / a.step) * a.step   # snap to the grid
        new = []
        for k, ((s, w), p) in enumerate(zip(syl, pitches)):
            off, ln = notes_[k][0], notes_[k][1]
            b0, bt0 = clk._position(o + off); b1, bt1 = clk._position(o + off + ln)
            t0 = clk.t(b0, bt0, extrapolate=True)[0]; t1 = clk.t(b1, bt1, extrapolate=True)[0]
            new.append({"t": round(t0, 3), "end": round(t1, 3), "pitch": p, "bar": b0, "beat": round(bt0, 3), "text": s, "kind": "note" if s else "unsung", "word": w, "placed": "dictated by the composer"})
        prev_end_o = o + notes_[-1][0] + notes_[-1][1]
        # the dictated line replaces (a) the same words where they sit now and (b) anything that overlaps its time span
        first_w = syl[0][1]; last_w = syl[-1][1]
        i0 = next((i for i, r in enumerate(rows) if r["kind"] == "note" and r.get("word") == first_w), None)
        removed = 0
        if i0 is not None:
            i1 = next((i for i in range(i0, len(rows)) if rows[i].get("word") == last_w), i0)
            while i1 + 1 < len(rows) and rows[i1 + 1]["kind"] == "slur":
                i1 += 1
            removed += i1 - i0 + 1; rows = rows[:i0] + rows[i1 + 1:]
        span0, span1 = new[0]["t"], new[-1]["end"]
        before = len(rows); rows = [r for r in rows if not (r["t"] < span1 and r["end"] > span0)]; removed += before - len(rows)
        rows = sorted(rows + new, key=lambda r: r["t"])
        report.append(f"'{words}': {len(new)} even notes from {new[0]['t']:.2f} s (bar {new[0]['bar']}:{new[0]['beat']:g}) to {new[-1]['end']:.2f} s, replacing {removed} note(s); pitches {' '.join(NAMES[p % 12] + str(p // 12 - 1) for p in pitches)}")
    # no overlaps
    rows.sort(key=lambda r: r["t"])
    for x, y in zip(rows, rows[1:]):
        if x["end"] > y["t"]:
            x["end"] = y["t"]
    for k, r in enumerate(rows):
        r["index"] = k
    sc["rows"] = rows; sc.setdefault("report", []).extend(report)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    json.dump(sc, open(out / "score.json", "w"), indent=1, ensure_ascii=False)
    q = notate.quantise([dict(r) for r in rows], clk, 4)
    notate.write_abc(q, out / "fit.abc", a.title); notate.write_musicxml(q, out / "fit.musicxml", a.title, 4); notate.engrave(out / "fit.musicxml", out / "fit.svg", out / "fit.png")
    for r in report:
        print("DICTATE:", r)


if __name__ == "__main__":
    main()
