"""fitlib.py — the project's fit as the Score Canvas numbers it, the sounds the singer gets, and edits by row (plain python).

Used by show_fit.py and edit_fit.py. Everything is found through the project file (arrange-project.json):
  fit          the fit (lyric-fit.json format, references/fit-format.md)
  pronounce    the composer's pronunciations ({"Footsteps": ["F UH1", "T S EH1 P S"]}); created as
               pronounce.json beside the project file on the first pronounce edit if the project has none
  analysis     the tempo map the canvas is drawn on (analysis, else analysis_measured), with beat_offset,
               so bar and beat here are the bar and beat the canvas shows (the composer's count)
The sounds come from phonemes.py run with the configured g2p python (setting python.soulx).
"""
import json, math, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
import arrange_config  # noqa: E402
from clock import Clock  # noqa: E402
from feel import feel, subdivision  # noqa: E402

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


class Canvas:
    """Bar and beat in the composer's count, as the canvas prints them, to and from seconds in the recording."""

    def __init__(self, analysis, beat_offset=0.0):
        self.clk = Clock(analysis)
        self.per, self.bpb, self.ts = feel(analysis)
        self.offset = float(beat_offset)   # in the composer's beats, as studio.py passes --beat-offset
        self.steps = subdivision(self.ts)   # beats are shown to the nearest quarter (thirds in compound time)

    def _ordinal(self, t):
        bar, beat = self.clk.at(t, extrapolate=True)
        return self.clk._ordinal(bar, beat)

    def pos(self, t):
        bc = round((self._ordinal(t) * self.per + self.offset) * self.steps) / self.steps
        bar = math.floor(bc / self.bpb) + 1
        return bar, round(bc - (bar - 1) * self.bpb + 1, 3)

    def t_of(self, bar, beat):
        bc = (int(bar) - 1) * self.bpb + float(beat) - 1
        if not 0 <= float(beat) - 1 < self.bpb:
            raise ValueError(f"beat {beat} is outside a bar of {self.bpb} beats")
        bar_m, beat_m = self.clk._position((bc - self.offset) / self.per)
        return round(self.clk.t(bar_m, beat_m, extrapolate=True)[0], 3)


def load(project):
    proj, base = arrange_config.project(project)
    fit = json.load(open(proj["fit"]))
    pron_path = Path(proj["pronounce"]) if proj.get("pronounce") else None
    pron = json.load(open(pron_path)) if pron_path and pron_path.exists() else {}
    canvas = Canvas(json.load(open(proj.get("analysis") or proj["analysis_measured"])), proj.get("beat_offset", 0))
    return {"project": Path(project), "base": base, "proj": proj, "fit": fit, "pron": pron, "pron_path": pron_path, "canvas": canvas}


def save(P, rows, pron):
    for k, r in enumerate(rows):
        r["index"] = k
    P["fit"]["rows"] = rows
    json.dump(P["fit"], open(P["proj"]["fit"], "w"), indent=1, ensure_ascii=False)
    if pron != P["pron"] or (pron and P["pron_path"] is None):
        path = P["pron_path"]
        if path is None:   # first pronunciation: a file beside the project, recorded in it so sing.py uses it
            path = P["base"] / "pronounce.json"
            raw = json.loads(P["project"].read_text()); raw["pronounce"] = path.name
            P["project"].write_text(json.dumps(raw, indent=1))
        json.dump(pron, open(path, "w"), indent=1, ensure_ascii=False)


def numbered(rows, canvas):
    """Each row with the canvas's bar.beat and grey number (syllables of a line counted from 1; a line starts after a gap of 1 s)."""
    out, num = [], 0
    for i, r in enumerate(rows):
        bar, beat = canvas.pos(r["t"])
        n = None
        if r["kind"] == "note":
            if i == 0 or r["t"] - rows[i - 1]["end"] >= 1.0:
                num = 0
            num += 1; n = num
        out.append({**r, "_bar": bar, "_beat": beat, "_num": n})
    return out


def table(rows, canvas):
    lines = ["idx | bar.beat | no. | t - end (s) | pitch | kind | text | word"]
    for i, r in enumerate(numbered(rows, canvas)):
        lines.append(f"{i} | {r['_bar']}.{r['_beat']:g} | {r['_num'] or ''} | {r['t']:.3f} - {r['end']:.3f} | {nn(r['pitch'])} | {r['kind']} | {r.get('text') or ''} | {r.get('word') or ''}")
    return "\n".join(lines)


def sounds(rows, pron):
    py = arrange_config.load()["python"]["soulx"]   # the python with g2p_en, as sing.py uses
    with tempfile.TemporaryDirectory() as td:
        fi, fo, fp = Path(td) / "fit.json", Path(td) / "score.json", Path(td) / "pron.json"
        json.dump({"rows": [{k: r.get(k) for k in ("t", "end", "pitch", "text", "word", "kind")} for r in rows]}, open(fi, "w")); json.dump(pron or {}, open(fp, "w"))
        r = subprocess.run([py, str(HERE / "phonemes.py"), str(fi), str(fo), "--pronounce", str(fp)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError(f"phonemes.py failed: {r.stderr.strip()[-300:]}")
        d = json.load(open(fo)); rs = d["rows"] if isinstance(d, dict) else d
    return "\n".join(f"{float(x.get('t', 0)):.3f} {x.get('text')}: {x.get('phoneme')}" for x in rs)


def apply(rows, pron, ops, canvas):
    """Apply edits in order, all or nothing. Row numbers are those of `rows` before this call."""
    rows = [dict(r) for r in rows]; pron = dict(pron); idx = list(range(len(rows)))   # idx[k] = row k's number before these edits

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
            r["_edited"] = True
        elif o == "move":
            r = find(op["row"]); d = r["end"] - r["t"]
            r["t"] = canvas.t_of(op["bar"], op["beat"]); r["end"] = float(op["end"]) if "end" in op else round(r["t"] + d, 3); r["_edited"] = True
        elif o == "shift":
            for i in op["rows"]:
                r = find(i); r["t"] = round(r["t"] + float(op["by"]), 3); r["end"] = round(r["end"] + float(op["by"]), 3); r["_edited"] = True
        elif o == "insert":
            k = idx.index(int(op["after"])) + 1
            rows.insert(k, {"t": float(op["t"]), "end": float(op["end"]), "pitch": to_midi(op["pitch"]), "kind": op.get("kind", "note"),
                            "text": op.get("text", ""), "word": op.get("word"), "placed": "by the composer", "_edited": True})
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
        if r["kind"] not in ("note", "slur", "unsung"):
            raise ValueError(f"row {i}: kind must be note, slur or unsung, not {r['kind']!r}")
    rows.sort(key=lambda r: (r["t"], r["end"]))
    for r in rows:
        if r.pop("_edited", False):
            r.pop("phoneme", None)   # recomputed by phonemes.py at the next sing
            r["bar"], r["beat"] = canvas.pos(r["t"])
    return rows, pron
