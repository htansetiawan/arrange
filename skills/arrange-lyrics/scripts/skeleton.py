#!/usr/bin/env python3
"""skeleton.py — the melody inside the piano for a bar range, as phrases with numbered syllable slots (/arrange-lyrics step 2-3; analysis python).

    python skeleton.py --analysis piano-analysis.json --midi piano.mid --bars 1 8 -o jobs/skeleton-1-8/ [--lyrics lines.txt] [--title "..."]

Listens to the transcription for the bars asked: the top voice at each attack
(notes from middle C up unless the line sits lower), short ornaments dropped,
each note cut at the next attack. Phrases are split where the line pauses or
holds. Each phrase gets its syllable slots (a note can carry a syllable if it
starts after a gap, lasts long enough, or leads into a long note; the rest of
a fast run holds the previous syllable). Writes skeleton.json, a notation
picture with the slot numbers under the notes, an ABC, and, with --lyrics,
a proposal: for each phrase the line of the composer's whose syllable count
is nearest, with the fitting trick applied and explained in words (split a
long note into two repeated notes for an extra syllable; hold the last
syllable over a spare note). The composer says yes, no, or which phrase to
work on.
"""
import argparse, json, re, sys
from pathlib import Path

import pretty_midi

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock, ClockError  # noqa: E402
import notate  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def melody_in_bars(midi, clk, b0, b1, floor=58, min_dur=0.12):
    t0 = clk.t(b0, 1)[0]; t1 = clk.bar_end(b1)[0]
    pm = pretty_midi.PrettyMIDI(midi)
    notes = sorted((float(n.start), float(n.end), int(n.pitch), int(n.velocity)) for i in pm.instruments for n in i.notes if t0 - 0.05 <= n.start < t1)
    clusters, cur = [], []
    for n in notes:
        if cur and n[0] - cur[0][0] > 0.04:
            clusters.append(cur); cur = []
        cur.append(n)
    if cur:
        clusters.append(cur)
    tops = []
    for c in clusters:
        hi = [n for n in c if n[2] >= floor] or c
        tops.append(max(hi, key=lambda n: n[2]))
    line = []
    for k, n in enumerate(tops):
        end = n[1]
        if k + 1 < len(tops):
            end = min(end, tops[k + 1][0])
        if end - n[0] >= min_dur:
            line.append({"t": round(n[0], 3), "end": round(end, 3), "pitch": n[2], "vel": n[3]})
    for r in line:
        try:
            bar, beat = clk.at(r["t"]); r["bar"], r["beat"] = bar, round(beat, 2)
        except ClockError:
            r["bar"], r["beat"] = None, None
    return line


def phrases_of(line, gap_s=0.4, hold_s=1.5, min_slots=6, big_gap_s=1.2):
    """Motifs end at a rest or a held note; motifs are joined into phrases of at least `min_slots` notes unless a long rest separates them."""
    motifs, cur = [], []
    for k, r in enumerate(line):
        if cur:
            prev = line[k - 1]
            if r["t"] - prev["end"] >= gap_s or (prev["end"] - prev["t"]) >= hold_s:
                motifs.append(cur); cur = []
        cur.append(k)
    if cur:
        motifs.append(cur)
    out, acc = [], []
    for m in motifs:
        if acc:
            gap = line[m[0]]["t"] - line[acc[-1]]["end"]
            if len(acc) >= min_slots or gap >= big_gap_s:
                out.append(acc); acc = []
        acc += m
    if acc:
        if out and len(acc) < 3:
            out[-1] += acc
        else:
            out.append(acc)
    return out


def slots_of(line, min_s=0.2):
    s = []
    for k, r in enumerate(line):
        dur = r["end"] - r["t"]; after_gap = k == 0 or r["t"] - line[k - 1]["end"] > 0.1
        nd = (line[k + 1]["end"] - line[k + 1]["t"]) if k + 1 < len(line) else 0
        pd = (line[k - 1]["end"] - line[k - 1]["t"]) if k else 1
        s.append(after_gap or dur >= min_s or (dur < min_s and nd >= 2 * min_s and pd >= min_s))
    return s


def syllables(word, g2p=None):
    if g2p:
        ph = [p for p in g2p(word) if re.fullmatch(r"[A-Z]+[012]?", p)]
        return max(1, sum(1 for p in ph if re.match(r"[AEIOU]", p)))
    m = re.findall(r"[aeiouy]+", word.lower()); n = len(m)
    if word.lower().endswith("e") and n > 1 and not word.lower().endswith(("le", "ee", "ye")):
        n -= 1
    return max(1, n)


def propose(phrases, line, slots, lines, max_diff=3):
    """For each phrase pick the unused line with the nearest syllable count; apply split or hold for a difference of one or two."""
    used, props = set(), []
    counts = [(ln, sum(syllables(w) for w in re.findall(r"[A-Za-z']+", ln))) for ln in lines]
    for pi, ph in enumerate(phrases):
        have = sum(1 for k in ph if slots[k])
        best = min(((abs(c - have), i) for i, (ln, c) in enumerate(counts) if i not in used), default=None)
        if best is None:
            props.append({"phrase": pi + 1, "slots": have, "line": None, "note": "no line left to propose"}); continue
        d, i = best
        if d > max_diff:
            props.append({"phrase": pi + 1, "slots": have, "line": None, "note": f"no line of the composer's is within {max_diff} syllables of {have} slots; placeholder 'la' or an instrumental phrase"}); continue
        used.add(i); ln, c = counts[i]
        trick, ops = "fits one syllable per slot", []
        if c > have:
            longest = sorted((k for k in ph if slots[k]), key=lambda k: -(line[k]["end"] - line[k]["t"]))[:c - have]
            ops = [{"op": "split", "note": k, "why": f"'{ln}' has {c} syllables for {have} slots: split the {NAMES[line[k]['pitch'] % 12]}{line[k]['pitch'] // 12 - 1} at bar {line[k]['bar']} into two repeated notes"} for k in longest]
            trick = f"{c - have} more syllable(s) than slots: repeat the longest note(s) so two syllables share the pitch (as 'lan-terns')"
        elif c < have:
            spare = [k for k in ph if slots[k]][c:]
            ops = [{"op": "hold", "note": k, "why": f"'{ln}' has {c} syllables for {have} slots: the {NAMES[line[k]['pitch'] % 12]}{line[k]['pitch'] // 12 - 1} at bar {line[k]['bar']} holds the previous syllable"} for k in spare]
            trick = f"{have - c} fewer syllable(s) than slots: the last word is held over the spare note(s)"
        props.append({"phrase": pi + 1, "slots": have, "line": ln, "syllables": c, "trick": trick, "ops": ops})
    return props


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True); ap.add_argument("--midi", required=True); ap.add_argument("--bars", type=int, nargs=2, required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--lyrics"); ap.add_argument("--title"); ap.add_argument("--floor", type=int, default=58)
    ap.add_argument("--melody-json", help="an already extracted melody on a quarter grid at twice the map's tempo (a JSON list of [start_q, dur_q, pitch, vel]) instead of the raw transcription")
    ap.add_argument("--max-diff", type=int, default=3, help="propose a line only when its syllable count is within this many of the phrase's slots")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    an = json.load(open(a.analysis)); clk = Clock(an)
    if a.melody_json:
        from fractions import Fraction
        mj = json.load(open(a.melody_json)); t0 = clk.t(a.bars[0], 1)[0]; t1 = clk.bar_end(a.bars[1])[0]
        line = []
        for q, d, pitch, vel in mj["melody"]:
            o = float(Fraction(q)) / 2.0; oe = o + float(Fraction(d)) / 2.0   # one quarter of the fast grid = half a beat of the map
            try:
                bar, beat = clk._position(o); st = clk.t(bar, beat)[0]; be, bb = clk._position(oe); en = clk.t(be, bb, extrapolate=True)[0]
            except ClockError:
                continue
            if t0 - 0.05 <= st < t1:
                line.append({"t": round(st, 3), "end": round(en, 3), "pitch": int(pitch), "vel": int(vel), "bar": bar, "beat": round(beat, 2)})
        for x, y in zip(line, line[1:]):
            x["end"] = min(x["end"], y["t"]) if y["t"] > x["t"] else x["end"]
    else:
        line = melody_in_bars(a.midi, clk, a.bars[0], a.bars[1], a.floor)
    if not line:
        sys.exit(f"no melody notes found in bars {a.bars[0]}-{a.bars[1]}")
    ph = phrases_of(line); sl = slots_of(line)
    title = a.title or f"Bars {a.bars[0]}–{a.bars[1]}: the line in the piano, with syllable slots"
    # notation rows: slot numbers as the words, holds as ~
    rows, n = [], 0
    for k, r in enumerate(line):
        if sl[k]:
            n += 1; rows.append({**r, "text": str(n), "kind": "note", "word": str(n)})
        else:
            rows.append({**r, "text": "~", "kind": "slur", "word": None})
    q = notate.quantise(rows, clk, 4)
    notate.write_abc(q, out / "skeleton.abc", title)
    kinfo = json.load(open(a.analysis)).get("key") or {}
    notate.write_musicxml(q, out / "skeleton.musicxml", title, 4, key_name=kinfo.get("tonic", "F"), mode=kinfo.get("mode", "major"))
    notate.engrave(out / "skeleton.musicxml", out / "skeleton.svg", out / "skeleton.png")
    report = [f"bars {a.bars[0]}–{a.bars[1]} ({clk.t(a.bars[0], 1)[0]:.1f}–{clk.bar_end(a.bars[1])[0]:.1f} s): {len(line)} melody notes in {len(ph)} phrase(s)"]
    for pi, p in enumerate(ph):
        first, last = line[p[0]], line[p[-1]]
        report.append(f"phrase {pi + 1}: bars {first['bar']}–{last['bar']}, {len(p)} notes, {sum(1 for k in p if sl[k])} syllable slots, {NAMES[min(line[k]['pitch'] for k in p) % 12]}{min(line[k]['pitch'] for k in p) // 12 - 1}–{NAMES[max(line[k]['pitch'] for k in p) % 12]}{max(line[k]['pitch'] for k in p) // 12 - 1}, {first['t']:.1f}–{last['end']:.1f} s")
    props = []
    if a.lyrics:
        lines = [ln.strip() for ln in Path(a.lyrics).read_text().splitlines() if ln.strip() and not ln.startswith("[")]
        props = propose(ph, line, sl, lines, a.max_diff)
        for pr in props:
            if not pr.get("line"):
                report.append(f"phrase {pr['phrase']}: {pr['note']}")
            if pr.get("line"):
                report.append(f"phrase {pr['phrase']} ← '{pr['line']}' ({pr['syllables']} syllables for {pr['slots']} slots): {pr['trick']}")
                for op in pr["ops"]:
                    report.append("   " + op["why"])
    json.dump({"bars": a.bars, "line": line, "phrases": ph, "slots": sl, "proposals": props, "report": report}, open(out / "skeleton.json", "w"), indent=1, ensure_ascii=False)
    (out / "report.txt").write_text("\n".join(report) + "\n")
    for r in report:
        print(r)


if __name__ == "__main__":
    main()
