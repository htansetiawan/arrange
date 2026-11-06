"""fitlib.py — the sung line (fit) as the score canvas numbers it, the sounds the singer gets, and edits by row.

The project folder (default ./song) holds fit.json (rows: t, end, pitch, text, word, kind, bar, beat, num),
pronounce.json and clock.json (canvas bar:quarter-beat -> seconds in the recording).
"""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY_G2P = os.environ.get("ARRANGE_G2P_PY", sys.executable)   # a Python with g2p_en (the sounds step)
NOTE = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def nn(p):
    return f"{NOTE[p % 12]}{p // 12 - 1}" if isinstance(p, int) else str(p)


def to_midi(x):
    if isinstance(x, (int, float)):
        return int(x)
    m = re.match(r"^\s*([A-Ga-g])([#b♯♭]?)(-?\d)\s*$", str(x))
    if not m:
        raise ValueError(f"not a note: {x}")
    return {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1).upper()] + {"#": 1, "♯": 1, "b": -1, "♭": -1, "": 0}[m.group(2)] + 12 * (int(m.group(3)) + 1)


def load(song):
    D = Path(song)
    fit = json.load(open(D / "fit.json")); pron = json.load(open(D / "pronounce.json")); clock = json.load(open(D / "clock.json"))
    return fit, pron, clock


def save(song, fit, pron):
    D = Path(song)
    json.dump(fit, open(D / "fit.json", "w"), indent=1, ensure_ascii=False); json.dump(pron, open(D / "pronounce.json", "w"), indent=1, ensure_ascii=False)


def t_of(clock, bar, beat):
    k = f"{int(bar)}:{int(round((float(beat) - 1) * 4))}"
    if k not in clock:
        raise ValueError(f"no canvas position {bar}.{beat}")
    return clock[k]


def renumber(rows, clock):
    """bar.beat of rows whose time changed (nearest quarter beat on the canvas clock) and the grey numbers per line."""
    pts = sorted((v, k) for k, v in clock.items())
    line, num = 0, 0
    for i, r in enumerate(rows):
        if r.get("_moved") or r.get("bar") is None:
            v, k = min(pts, key=lambda p: abs(p[0] - r["t"]))
            b, q = k.split(":"); r["bar"], r["beat"] = int(b), round(int(q) / 4 + 1, 3)
            r.pop("_moved", None)
        if r["kind"] == "note":
            if i == 0 or r["t"] - rows[i - 1]["end"] >= 1.0:
                line += 1; num = 0
            num += 1; r["num"] = num
        else:
            r["num"] = None
    return rows


def table(rows):
    lines = ["idx | bar.beat | no. | t - end (s) | pitch | kind | text | word"]
    for i, r in enumerate(rows):
        lines.append(f"{i} | {r['bar']}.{r['beat']:g} | {r['num'] or ''} | {r['t']:.3f} - {r['end']:.3f} | {nn(r['pitch'])} | {r['kind']} | {r['text']} | {r['word'] or ''}")
    return "\n".join(lines)


def sounds(rows, pron):
    with tempfile.TemporaryDirectory() as td:
        fi, fo, fp = Path(td) / "fit.json", Path(td) / "score.json", Path(td) / "pron.json"
        json.dump({"rows": [{k: r.get(k) for k in ("t", "end", "pitch", "text", "word", "kind")} for r in rows]}, open(fi, "w")); json.dump(pron or {}, open(fp, "w"))
        r = subprocess.run([PY_G2P, str(HERE / "phonemes.py"), str(fi), str(fo), "--pronounce", str(fp)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError(f"phonemes.py failed: {r.stderr[-300:]}")
        d = json.load(open(fo)); rs = d["rows"] if isinstance(d, dict) else d
    return "\n".join(f"{float(x.get('t', 0)):.3f} {x.get('text')}: {x.get('phoneme')}" for x in rs)


def apply(rows, pron, ops, clock):
    rows = [dict(r) for r in rows]; idx = list(range(len(rows)))   # idx[k] = row k as it was numbered before these edits

    def find(i):
        if int(i) not in idx:
            raise KeyError(f"no row {i}")
        return rows[idx.index(int(i))]
    for op in ops:
        o = op.get("op")
        if o == "set":
            r = find(op["row"])
            for k in ("text", "kind", "word", "t", "end"):
                if k in op:
                    r[k] = float(op[k]) if k in ("t", "end") else op[k]
            if "pitch" in op:
                r["pitch"] = to_midi(op["pitch"])
            if "t" in op:
                r["_moved"] = True
        elif o == "move":
            r = find(op["row"]); d = r["end"] - r["t"]
            r["t"] = t_of(clock, op["bar"], op["beat"]); r["end"] = float(op["end"]) if "end" in op else r["t"] + d; r["_moved"] = True
        elif o == "shift":
            for i in op["rows"]:
                r = find(i); r["t"] += float(op["by"]); r["end"] += float(op["by"]); r["_moved"] = True
        elif o == "insert":
            k = idx.index(int(op["after"])) + 1
            rows.insert(k, {"t": float(op["t"]), "end": float(op["end"]), "pitch": to_midi(op["pitch"]), "kind": op.get("kind", "note"),
                            "text": op.get("text", ""), "word": op.get("word"), "bar": None, "beat": None, "num": None})
            idx.insert(k, None)
        elif o == "delete":
            k = idx.index(int(op["row"])); rows.pop(k); idx.pop(k)
        elif o == "pronounce":
            pron[op["word"]] = op["sounds"]
        else:
            raise ValueError(f"unknown edit {o!r}")
    for i, r in enumerate(rows):
        if r["end"] <= r["t"]:
            raise ValueError(f"row {i} would end before it starts ({r['t']:.3f} - {r['end']:.3f})")
    rows.sort(key=lambda r: (r["t"], r["end"]))
    return renumber(rows, clock), pron
