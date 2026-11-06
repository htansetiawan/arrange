#!/usr/bin/env python3
"""notate.py — a sung reference, transcribed by SoulX's preprocessing, into the fit, MusicXML, ABC and a picture (/arrange-lyrics; analysis python).

    python notate.py --metadata reference-pre/metadata.json --analysis piano-analysis.json --window 68 118 -o jobs/L1/ [--title "..."] [--feel fast]

SoulX's pipeline (vocal extraction, lyric recognition, note transcription)
writes metadata.json: segments of tokens, each a word or a rest with its
phoneme, duration, MIDI pitch and type (1 rest, 2 note, 3 held). This turns
that into:
  lyric-fit.json   one row per note in the fit format, absolute seconds, sung
                   pitch (the singer's own octave), phonemes as recognised
  melody.musicxml  the line as notation with the words under the notes, in
                   the composer's feel (one notated bar = half a bar of the
                   slow map), quantised to sixteenths
  melody.abc       the same in ABC with a w: lyric line
  melody.svg/.png  engraved by Verovio (and a PNG via headless Chrome or Chromium if present:
                   the `chrome` setting / ARRANGE_CHROME, else google-chrome or chromium on PATH)
  report.txt       what was recognised, what was quantised, what was unsure
Words come from the recognizer and may be wrong; the composer's own lines are
the truth, and `--lyrics` with them swaps the recognised words for theirs where
the counts agree (reported where they do not).
"""
import argparse, json, re, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clock import Clock  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def rows_from_metadata(meta, window):
    rows = []
    for seg in meta:
        t0 = seg["time"][0] / 1000.0
        durs = [float(x) for x in seg["duration"].split()]
        texts = seg["text"].split(); phs = seg["phoneme"].split(); pitches = [int(x) for x in seg["note_pitch"].split()]; types = [int(x) for x in seg["note_type"].split()]
        n = min(len(durs), len(texts), len(phs), len(pitches), len(types))
        t = t0
        for k in range(n):
            st, en = t, t + durs[k]; t = en
            if en < window[0] or st > window[1]:
                continue
            if types[k] == 1 or texts[k] in ("<SP>", "<AP>") or pitches[k] == 0:
                continue
            rows.append({"t": round(st, 3), "end": round(en, 3), "pitch": pitches[k], "text": texts[k] if types[k] == 2 else "~", "phoneme": phs[k],
                         "kind": "note" if types[k] == 2 else "slur", "word": texts[k], "placed": "transcribed from the reference singer by SoulX preprocessing"})
    return rows


def quantise(rows, clk, steps_per_beat=4):
    """Snap to the slow map at `steps_per_beat` (4 = sixteenths of the composer's fast feel). Returns rows with bar/beat and quantised times."""
    grid = []
    for i, b in enumerate(clk.beats):
        nxt = clk.beats[i + 1]["t"] if i + 1 < len(clk.beats) else b["t"] + clk.last_dur
        for k in range(steps_per_beat):
            grid.append((b["t"] + (nxt - b["t"]) * k / steps_per_beat, clk._ordinal(b["bar"], b["beat"]) + k / steps_per_beat))
    import bisect
    ts = [g[0] for g in grid]
    def near(t):
        i = bisect.bisect_left(ts, t); c = [j for j in (i - 1, i) if 0 <= j < len(grid)]
        return min(c, key=lambda j: abs(ts[j] - t))
    out = []
    for r in rows:
        i0, i1 = near(r["t"]), near(r["end"])
        if i1 <= i0:
            i1 = min(i0 + 1, len(grid) - 1)
        o0, o1 = grid[i0][1], grid[i1][1]
        bar, beat = clk._position(o0)
        out.append({**r, "t_sung": r["t"], "end_sung": r["end"], "t": round(ts[i0], 3), "end": round(ts[i1], 3), "ordinal": o0, "steps": int(round((o1 - o0) * steps_per_beat)), "bar": bar, "beat": round(beat, 3)})
    for a, b in zip(out, out[1:]):
        if a["end"] > b["t"]:
            a["end"] = b["t"]; a["steps"] = max(1, int(round((b["ordinal"] - a["ordinal"]) * steps_per_beat)))
    return [r for r in out if r["end"] > r["t"]]


def abc_pitch(m):
    pc = m % 12; octv = m // 12 - 1
    letter = {0: "C", 1: "^C", 2: "D", 3: "_E", 4: "E", 5: "F", 6: "^F", 7: "G", 8: "_A", 9: "A", 10: "_B", 11: "B"}[pc]
    if octv >= 5:
        return letter.lower() + "'" * (octv - 5)
    return letter + "," * (4 - octv)


def write_abc(rows, path, title, key="F", bpm=92, steps_per_beat=4):
    """Composer's feel: a notated 4/4 bar = 2 slow beats = 8 steps; L:1/8 so one step = one eighth."""
    steps_per_bar = 2 * steps_per_beat
    first = int(rows[0]["ordinal"] * steps_per_beat); first_bar_start = first - first % steps_per_bar
    body, lyr, pos = [], [], first_bar_start
    def emit(tok, n):
        nonlocal pos
        body.append(tok + (str(n) if n != 1 else "")); pos += n
    cur_bar = first_bar_start // steps_per_bar
    for r in rows:
        s = int(round(r["ordinal"] * steps_per_beat)); n = max(1, r["steps"])
        while s > pos:   # rest, split at bar lines
            room = steps_per_bar - (pos - first_bar_start) % steps_per_bar; k = min(room, s - pos); emit("z", k)
            if (pos - first_bar_start) % steps_per_bar == 0: body.append("|")
        while n > 0:   # note, tied across bar lines
            room = steps_per_bar - (pos - first_bar_start) % steps_per_bar; k = min(room, n); emit(abc_pitch(r["pitch"]), k); n -= k
            if n > 0: body.append("-")
            if (pos - first_bar_start) % steps_per_bar == 0: body.append("|")
        lyr.append("_" if r["kind"] == "slur" else r["text"].replace(" ", "~"))
    head = f"X:1\nT:{title}\nM:4/4\nL:1/8\nQ:1/4={bpm}\nK:{key}\n"
    # break the body into lines of 4 bars
    out, line, bars = [], [], 0
    for tok in body:
        line.append(tok)
        if tok == "|":
            bars += 1
            if bars % 4 == 0:
                out.append(" ".join(line)); line = []
    if line:
        out.append(" ".join(line))
    text = head + "\n".join(out) + "\n" + "w: " + " ".join(lyr) + "\n"
    Path(path).write_text(text); return text


def write_musicxml(rows, path, title, steps_per_beat=4, line_numbers=False, chords=None, line_labels=False, key_name="F", mode="major", bpm=92, per=2, ts="4/4"):
    """`line_numbers`: a second lyric line with the note's number within its line. `chords`: [(notated bar, name)] shown above the staff.
    `per`: the composer's beats (quarters) per map beat; `ts`: the notated time signature (see feel.py)."""
    from feel import beats_per_bar, beat_ql
    bpb = beats_per_bar(ts); u = beat_ql(ts)   # the composer's beats per bar; the composer's beat in quarter lengths (1.5 in 12/8)
    from music21 import stream, note, meter, key, tempo, duration, metadata, spanner, clef
    s = stream.Score(); s.metadata = metadata.Metadata(title=title)
    import statistics
    p = stream.Part(); p.insert(0, clef.BassClef() if statistics.median(r["pitch"] for r in rows) < 60 else clef.TrebleClef())
    p.insert(0, meter.TimeSignature(ts)); kk = key.Key(key_name, mode); p.insert(0, kk); p.insert(0, tempo.MetronomeMark(number=bpm, referent=duration.Duration(u)))
    q = 1.0 / steps_per_beat * per * u   # one step in quarter lengths of the composer's feel (a map beat = `per` of the composer's quarters)
    first = rows[0]["ordinal"]; first_bar = int(first * per // bpb)
    offset0 = first_bar * bpb / per   # map ordinal where the first notated bar starts
    pos = offset0 * per * u
    prev_note, hold_from = None, None
    line_no, in_line = 0, 0
    word_acc = ""   # letters of the current word sung so far, for hyphens between its syllables
    for i, r in enumerate(rows):
        start = r["ordinal"] * per * u; ql = max(q, r["steps"] * q)
        if start > pos + 1e-6:
            rest = note.Rest(); rest.duration = duration.Duration(start - pos); p.append(rest); pos = start
        from music21 import pitch as m21pitch
        spell = {1: "D-", 3: "E-", 6: "F#", 8: "A-", 10: "B-"} if kk.sharps <= 0 else {1: "C#", 3: "D#", 6: "F#", 8: "G#", 10: "A#"}   # flat keys spell flat (F# stays), sharp keys sharp
        pc = r["pitch"] % 12
        n = note.Note(m21pitch.Pitch(spell[pc] + str(r["pitch"] // 12 - 1)) if pc in spell else r["pitch"]); n.duration = duration.Duration(ql)
        if r["kind"] == "note":
            n.lyric = r["text"]
            target = "".join(ch for ch in (r.get("word") or "") if ch.isalpha()).lower()
            piece = "".join(ch for ch in r["text"] if ch.isalpha()).lower()
            if target and piece and target != piece and target.startswith(word_acc + piece):
                first = word_acc == ""; word_acc += piece; last = word_acc == target
                n.lyrics[0].syllabic = "begin" if first else ("end" if last else "middle")
                if last:
                    word_acc = ""
            else:
                word_acc = ""
        if line_numbers and r["kind"] == "note":
            if i == 0 or r["t"] - rows[i - 1]["end"] >= 1.0:
                line_no += 1; in_line = 0
            in_line += 1
            n.lyrics.append(note.Lyric(text=str(in_line), number=2))
        p.append(n); pos = start + ql
        if r["kind"] == "slur" and prev_note is not None:
            p.insert(0, spanner.Slur(prev_note, n))
        prev_note = n
    # chord symbols and line labels are inserted only after every note is appended (append places at the stream's end)
    if chords:
        from music21 import expressions as _ex
        for bar_no, name in chords:
            off = (bar_no - first_bar - 1) * float(bpb) * u
            if 0 <= off <= (rows[-1]["ordinal"] * per - offset0 * per + bpb) * u:
                te = _ex.TextExpression(name); te.placement = "above"; te.style.fontStyle = "normal"; te.style.fontSize = 10; p.insert(off, te)
    # a label above the first note of each line: time in the recording and the bar of the composer's map
    from music21 import expressions
    starts = [r for i, r in enumerate(rows) if r["kind"] == "note" and (i == 0 or r["t"] - rows[i - 1]["end"] >= 1.0)] if line_labels else []
    for r in starts:
        nb = int(r["ordinal"] * per // bpb) + 1
        te = expressions.TextExpression(f"{r.get('t_sung', r['t']):.1f} s · recording bar {r.get('bar', '?')} · notated bar {nb}"); te.placement = "above"; te.style.fontSize = 9
        p.insert((r["ordinal"] * per - offset0 * per) * u, te)
    p.makeMeasures(inPlace=True)
    try:
        p.makeTies(inPlace=True)
    except Exception:
        pass
    # accidentals: only what the key does not already say, no naturals on every note
    ks = key.KeySignature(kk.sharps)
    for i, m in enumerate(p.getElementsByClass("Measure")):
        m.number = first_bar + 1 + i
        for n in m.notes:
            if n.pitch.accidental is not None and n.pitch.accidental.name == "natural":
                n.pitch.accidental = None
        m.makeAccidentals(useKeySignature=ks, overrideStatus=True, cautionaryPitchClass=False, cautionaryNotImmediateRepeat=False, inPlace=True)
    s.insert(0, p); s.write("musicxml", fp=str(path)); return path


def engrave(xml, svg, png=None):
    import verovio
    tk = verovio.toolkit(); tk.setOptions({"pageWidth": 3400, "pageHeight": 60000, "scale": 40, "adjustPageHeight": True, "breaks": "auto", "footer": "none", "header": "auto", "lyricSize": 5.0, "mnumInterval": 1})
    tk.loadFile(str(xml)); n = tk.getPageCount()
    pages = []
    for i in range(1, n + 1):
        out = Path(svg).with_name(Path(svg).stem + (f"-{i}" if n > 1 else "") + ".svg"); out.write_text(tk.renderToSVG(i)); pages.append(out)
    if png:
        import re as _re
        html = Path(svg).with_suffix(".html"); body = "".join(pg.read_text() for pg in pages)
        heights = [float(m) for m in _re.findall(r'<svg[^>]*height="([\d.]+)px"', body)] or [600.0]
        html.write_text("<!doctype html><meta charset=utf-8><body style='margin:0;background:#fff'>" + body)
        import arrange_config
        chrome = arrange_config.get(arrange_config.load(), "chrome") or next(
            (c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c)), None)
        if not chrome or not shutil.which(chrome):
            return pages   # no browser: the SVG pages stand; the PNG is skipped
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--window-size=1400,{int(sum(heights)) + 10}", f"--screenshot={png}", f"file://{html.resolve()}"], capture_output=True)
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--metadata", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--window", type=float, nargs=2, required=True)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--title", default="Melody heard in the reference"); ap.add_argument("--lyrics", help="the composer's own lines; replace recognised words where counts agree")
    ap.add_argument("--steps", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    meta = json.load(open(a.metadata)); clk = Clock(json.load(open(a.analysis)))
    raw = rows_from_metadata(meta, a.window)
    rows = quantise(raw, clk, a.steps)
    report = [f"{len(raw)} sung tokens between {a.window[0]}s and {a.window[1]}s in the recognizer's output ({sum(1 for r in raw if r['kind']=='note')} with a word, {sum(1 for r in raw if r['kind']=='slur')} held); {len(rows)} after quantising to {a.steps} steps per beat of the map",
              "words as recognised: " + " ".join(r["text"] for r in rows if r["kind"] == "note")]
    if a.lyrics:
        lines = [ln.strip() for ln in Path(a.lyrics).read_text().splitlines() if ln.strip()]
        import difflib
        mine = [w for ln in lines for w in re.findall(r"[A-Za-z']+", ln)]
        rec = [r for r in rows if r["kind"] == "note"]
        a_, b_ = [w.lower().strip("'") for w in mine], [r["text"].lower().strip("'") for r in rec]
        sm = difflib.SequenceMatcher(a=a_, b=b_, autojunk=False); replaced, kept = 0, []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace" and (i2 - i1) == (j2 - j1):
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    rec[j]["recognised"] = rec[j]["text"]; rec[j]["text"] = mine[i]; rec[j]["word"] = mine[i]; rec[j]["phoneme"] = ""; replaced += 1
            else:
                kept.append((tag, " ".join(mine[i1:i2]) or "—", " ".join(r["text"] for r in rec[j1:j2]) or "—"))
        report.append(f"the composer's {len(mine)} words aligned to the {len(rec)} recognised ones: {replaced} recognised word(s) replaced by the composer's where they sit one for one; phonemes for those are recomputed at render")
        for tag, m_, r_ in kept:
            report.append(f"  not replaced ({tag}): written '{m_}' against recognised '{r_}'")
    for k, r in enumerate(rows):
        r["index"] = k
    json.dump({"source": a.metadata, "window": a.window, "pitch_convention": "sung (the reference singer's own octave); render with shift 0", "lines": [], "rows": rows, "report": report}, open(out / "lyric-fit.json", "w"), indent=1, ensure_ascii=False)
    abc = write_abc(rows, out / "melody.abc", a.title)
    write_musicxml(rows, out / "melody.musicxml", a.title, a.steps)
    pages = engrave(out / "melody.musicxml", out / "melody.svg", out / "melody.png")
    report.append(f"notation: {len(pages)} page(s), feel = composer's 4/4 at 92 (one notated bar = half a bar of the slow map), quantised to sixteenths")
    (out / "report.txt").write_text("\n".join(report) + "\n")
    for r in report:
        print("NOTATE:", r)
    print(abc)


if __name__ == "__main__":
    main()
