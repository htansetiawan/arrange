#!/usr/bin/env python3
"""suite.py — E2-edits: curated edit requests on the score canvas (items.py), carried out by a model with vs without the
ARRANGE lyric skill's structure. Bar/beat and the grey syllable numbers are as the canvas shows them.

    python3 suite.py --build                 # canvas positions, gold rows, screenshots -> build/items.json, build/img/
    python3 suite.py --selftest              # gold scores correct, 'no change' fails, 'ask' passes only where asking is right
    python3 suite.py --model claude-sonnet-5-5 [--draws 3] [--arms typed bare] [--only cp01 ...] [--base-url URL]
    python3 suite.py --table                 # TABLE.md

Arms (same request, same fit, same screenshot when there is one):
  typed  ARRANGE notes + the fit as a table with the canvas's bar.beat and grey numbers + the sounds the singer gets +
         the edit list (set / move / shift / insert / delete / pronounce / ask)
  bare   the fit rows as JSON (canvas bar/beat) and the request; the answer is the whole edited rows, or a question
Both arms are told they may ask when the request is unclear. Scoring is by outcome: the edited fit must equal the gold
(start within 0.05 s, end within 0.10 s on the rows the edit touches, 0.02 s elsewhere; pitch, kind and text exact), or
pass the item's check (vague timing), or give the gold sounds (pronunciation). Incomplete items pass on a question with
no edit. Nothing here is a human study.
"""
import argparse, copy, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent; X = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "corrections")); sys.path.insert(0, str(HERE.parent / "revisions"))
import run_lyrics as L  # noqa: E402  (to_midi, nn, sounds, LIMIT)
import run_e2 as R  # noqa: E402  (backends, extract_json)
from items import ITEMS  # noqa: E402

BUILD = HERE / "build"; IMG = BUILD / "img"; RES = HERE / "results"
ANALYSIS_PY = os.environ.get("ARRANGE_ANALYSIS_PY", sys.executable)   # a Python with the analysis dependencies (docs/setup.md)
RUNS = Path(os.environ.get("ARRANGE_RUNS", X / "runs"))               # the song projects (not distributed)


# ---------------------------------------------------------------- build (analysis venv: canvas positions + clock)
def build():
    from canvas_pos import positions, canvas_clock
    IMG.mkdir(parents=True, exist_ok=True)
    songs = {}
    for song in sorted({it["song"] for it in ITEMS}):
        D = RUNS / song
        proj, an, fit, pos, (per, bpb, ts) = positions(D)
        pron = json.load(open(D / proj["pronounce"])) if proj.get("pronounce") else {}
        rows, line, num = [], 0, 0
        for i, (r, p) in enumerate(zip(fit["rows"], pos)):
            r = {k: r.get(k) for k in ("t", "end", "pitch", "text", "word", "kind", "placed")}
            r.update(bar=p["bar"], beat=p["beat"], num=None, line=None)
            if r["kind"] == "note":
                if i == 0 or r["t"] - fit["rows"][i - 1]["end"] >= 1.0:
                    line += 1; num = 0
                num += 1; r.update(num=num, line=line)
            rows.append(r)
        songs[song] = {"title": proj["title"], "rows": rows, "pron": pron, "ts": ts, "bpb": bpb, "per": per,
                       "canvas": str(D / proj.get("studio", "studio") / "score-canvas.html"), "t_of": canvas_clock(D)}
    out = []
    for it in ITEMS:
        s = songs[it["song"]]; rows = s["rows"]
        def res(v):
            if isinstance(v, tuple) and v[0] == "T":
                return round(s["t_of"](v[1], v[2]), 3)
            if isinstance(v, tuple) and v[0] == "mid":
                return round((rows[v[1]]["t"] + rows[v[1]]["end"]) / 2, 3)
            return v
        pron = s["pron"]
        if it.get("pre"):   # the item's starting fit: the canvas fit with earlier edits applied, rows renumbered
            pre = [{k: res(v) for k, v in op.items()} for op in it["pre"]]
            new, pron, _ = apply_ops({"before": rows, "pron_before": pron}, pre)
            for i, r in enumerate(new):
                if r.get("bar") is None:   # an inserted row: place it after the row before it (not engraved)
                    r.update(bar=new[i - 1]["bar"], beat=round(new[i - 1]["beat"] + 0.25, 3), num=None, line=None)
                r.pop("_o", None)
            rows = new
        gold = [{k: res(v) for k, v in op.items()} for op in it.get("gold", [])]
        alts = [[{k: res(v) for k, v in op.items()} for op in A] for A in it.get("alts", [])]
        rec = {k: v for k, v in it.items() if k not in ("gold", "alts", "pre")}
        rec.update(gold=gold, alts=alts, title=s["title"], ts=s["ts"], before=rows, pron_before=pron)
        if it.get("image"):
            png = IMG / f"{it['id']}.png"
            if not png.exists():
                subprocess.run([os.environ.get("ARRANGE_PLAYWRIGHT_PY", sys.executable), str(HERE / "shoot.py"), s["canvas"], str(png), *map(str, it["image"])], check=True)
            rec["image_path"] = str(png)
        out.append(rec)
    json.dump(out, open(BUILD / "items.json", "w"), indent=1, ensure_ascii=False)
    print(f"{len(out)} items -> {BUILD / 'items.json'}; {sum(bool(i.get('image')) for i in out)} screenshots in {IMG}")


def load():
    """The built items (with each song's fit) when present; otherwise the item definitions alone, which is enough for
    the tables. The fits are not distributed (copyrighted melodies), so --build, --selftest and runs need the projects."""
    f = BUILD / "items.json"
    return json.load(open(f)) if f.exists() else [dict(it) for it in ITEMS]


# ---------------------------------------------------------------- applying edits
def apply_ops(it, ops, t_of=None):
    rows = [dict(r, _o=i) for i, r in enumerate(copy.deepcopy(it["before"]))]
    pron = copy.deepcopy(it["pron_before"]); asked = []

    def find(i):
        hit = [r for r in rows if r.get("_o") == int(i)]
        if not hit:
            raise KeyError(f"no row {i}")
        return hit[0]
    for op in ops:
        o = op.get("op")
        if o == "set":
            r = find(op["row"])
            for k in ("text", "kind", "word", "t", "end"):
                if k in op:
                    r[k] = float(op[k]) if k in ("t", "end") else op[k]
            if "pitch" in op or "note" in op:   # 'note' accepted: the table once headed the pitch column 'note'
                r["pitch"] = L.to_midi(op.get("pitch", op.get("note")))
        elif o == "move":
            r = find(op["row"]); d = r["end"] - r["t"]
            if t_of is None:
                raise ValueError("move needs the canvas clock")
            r["t"] = t_of(int(op["bar"]), float(op["beat"])); r["end"] = float(op["end"]) if "end" in op else r["t"] + d
        elif o == "shift":
            for i in op["rows"]:
                r = find(i); r["t"] += float(op["by"]); r["end"] += float(op["by"])
        elif o == "insert":
            r = find(op["after"])
            rows.insert(rows.index(r) + 1, {"t": float(op["t"]), "end": float(op["end"]), "pitch": L.to_midi(op["pitch"]), "kind": op.get("kind", "note"),
                                            "text": op.get("text", ""), "word": op.get("word"), "placed": "inserted", "_o": None})
        elif o == "delete":
            rows.remove(find(op["row"]))
        elif o == "pronounce":
            pron[op["word"]] = op["sounds"]
        elif o in ("ask", "say"):   # a question to the composer, or an answer to his
            asked.append(op.get("question") or op.get("text"))
        else:
            raise ValueError(f"unknown op {o}")
    return rows, pron, asked


def apply_rows(it, obj):
    rows = []
    for r in obj["rows"]:
        rows.append({"t": float(r["t"]), "end": float(r["end"]), "pitch": L.to_midi(r["pitch"]), "kind": r.get("kind", "note"),
                     "text": r.get("text"), "word": r.get("word"), "_o": None})
    return rows, it["pron_before"], []


# ---------------------------------------------------------------- scoring
def ntext(r):
    k = r.get("kind"); t = (r.get("text") or "").strip().lower()
    return "~" if k == "slur" else ("" if k == "unsung" else t)


def same(a, b, tt, te, text=True):
    return (a.get("kind") == b.get("kind") and int(a["pitch"]) == int(b["pitch"]) and (not text or ntext(a) == ntext(b))
            and abs(a["t"] - b["t"]) <= tt and abs(a["end"] - b["end"]) <= te)


def unchanged(r, b):
    return same(r, b, 0.02, 0.02)


def gold_rows(it):
    rows, pron, _ = apply_ops(it, it["gold"])
    return rows, pron


def by_time(rows):
    return sorted(rows, key=lambda r: (round(r["t"], 3), r["end"]))


def diff_rows(it, rows, G):
    """rows vs gold rows G (both sorted by time). Returns (wrong on rows the gold changes, collateral elsewhere)."""
    B = it["before"]; rows, G = by_time(rows), by_time(G)
    if len(rows) != len(G):
        return [f"{len(rows)} rows, gold has {len(G)}"], []
    wrong, coll = [], []
    for r, g in zip(rows, G):
        touched = g.get("_o") is None or not unchanged(g, B[g["_o"]])
        if touched and not same(r, g, 0.05, 0.10):
            wrong.append(f"{L.nn(g['pitch'])} '{g.get('text')}' @{g['t']:.2f}-{g['end']:.2f}: got {L.nn(r['pitch'])} '{r.get('text')}' {r.get('kind')} @{r['t']:.2f}-{r['end']:.2f}")
        elif not touched and not unchanged(r, g):
            coll.append(f"changed {L.nn(g['pitch'])} '{g.get('text')}' @{g['t']:.2f} -> {L.nn(r['pitch'])} '{r.get('text')}' {r.get('kind')} @{r['t']:.2f}-{r['end']:.2f}")
    return wrong, coll


def check_timing(it, rows):
    B = it["before"]; rows = by_time(rows)
    if len(rows) != len(B):
        return [f"{len(rows)} rows, was {len(B)}"], []
    c = it["check"]; wrong, coll = [], []
    if "earlier" in c:
        k, p = c["earlier"]["row"], c["earlier"]["prev"]; r, b = rows[k], B[k]
        d = b["t"] - r["t"]
        if not (c["earlier"]["min"] <= d <= c["earlier"]["max"]):
            wrong.append(f"'{b['text']}' moved {d:+.2f} s earlier (want {c['earlier']['min']}-{c['earlier']['max']})")
        if not (abs(r["end"] - b["end"]) <= 0.05 or abs((b["end"] - r["end"]) - d) <= 0.05):
            wrong.append(f"'{b['text']}' end {r['end']:.2f} (was {b['end']:.2f})")
        if not (rows[p]["end"] <= r["t"] + 0.02 and rows[p]["end"] > rows[p]["t"]):
            wrong.append(f"'{B[p]['text']}' ends {rows[p]['end']:.2f}, after '{b['text']}' starts {r['t']:.2f}")
        named = {k, p}
    else:
        k, p = c["gap_before"]["row"], c["gap_before"]["prev"]
        gap = rows[k]["t"] - rows[p]["end"]
        if not (c["gap_before"]["min"] <= gap <= c["gap_before"]["max"]):
            wrong.append(f"gap before '{B[k]['text']}' {gap:.2f} s (want {c['gap_before']['min']}-{c['gap_before']['max']})")
        if abs(rows[k]["t"] - B[k]["t"]) > 0.02:
            wrong.append(f"'{B[k]['text']}' moved")
        if abs(rows[p]["t"] - B[p]["t"]) > 0.02:
            wrong.append(f"'{B[p]['text']}' start moved")
        named = {p}
    for i, (r, b) in enumerate(zip(rows, B)):
        if i in named:
            if r["pitch"] != b["pitch"] or ntext(r) != ntext(b) or r.get("kind") != b.get("kind"):
                coll.append(f"changed '{b['text']}' pitch/text")
        elif not unchanged(r, b):
            coll.append(f"changed {L.nn(b['pitch'])} '{b.get('text')}' @{b['t']:.2f}")
    return wrong, coll


def sung(rows, pron):
    return [x[1] for x in L.sounds([{k: v for k, v in r.items() if k != "_o"} for r in by_time(rows)], pron, "new")]


def check_sound(it, rows, pron):
    G, gp = gold_rows(it); B = it["before"]
    rows_s, G_s = by_time(rows), by_time(G)
    if len(rows_s) != len(G_s):
        return [f"{len(rows_s)} rows, gold has {len(G_s)}"], []
    wrong, coll = [], []
    for i, (r, g) in enumerate(zip(rows_s, G_s)):   # rows: same notes; text may differ only on the target rows
        if not same(r, g, 0.02, 0.02, text=i not in it["sound_rows"]):
            coll.append(f"changed {L.nn(g['pitch'])} '{g.get('text')}' @{g['t']:.2f}")
    Sm, Sg, Sb = sung(rows, pron), sung(G, gp), sung(B, it["pron_before"])
    if len(Sm) != len(Sg):
        return [f"{len(Sm)} sung rows, gold {len(Sg)}"], coll
    st = lambda p: re.sub(r"2", "1", p or "")
    for k in range(len(Sg)):
        if Sg[k] != Sb[k]:
            if st(Sm[k]) != st(Sg[k]):
                wrong.append(f"sounds {Sm[k]} want {Sg[k]}")
        elif st(Sm[k]) != st(Sb[k]):
            coll.append(f"sounds changed {Sb[k]} -> {Sm[k]}")
    return wrong, coll


def score(it, rows, pron, asked):
    edited = len(rows) != len(it["before"]) or any(not unchanged(r, b) for r, b in zip(by_time(rows), it["before"])) or pron != it["pron_before"]
    accept = it.get("accept", ["gold"])
    if it["kind"] == "question":
        txt = " ".join(map(str, asked)).lower()
        ok = not edited and all(k.lower() in txt for k in it["say"])
        return {"correct": ok, "outcome": "answered" if ok else ("edited" if edited else ("wrong answer" if asked else "no answer")),
                "wrong": [] if ok else [f"answer lacks {[k for k in it['say'] if k.lower() not in txt]}"], "collateral": []}
    if asked and not edited:
        return {"correct": "ask" in accept, "outcome": "asked", "wrong": [], "collateral": []}
    if not it["complete"] and "gold" not in accept:
        return {"correct": False, "outcome": "guessed", "wrong": ["edited instead of asking"], "collateral": []}
    if "check" in it:
        wrong, coll = check_timing(it, rows)
    elif it.get("sound_rows"):
        wrong, coll = check_sound(it, rows, pron)
    else:
        wrong, coll = diff_rows(it, rows, gold_rows(it)[0])
        for alt in it.get("alts", []):
            if wrong or coll:
                w2, c2 = diff_rows(it, rows, apply_ops(it, alt)[0])
                if not w2 and not c2:
                    wrong, coll = w2, c2
    ok = not wrong and not coll
    return {"correct": ok, "outcome": "correct" if ok else ("collateral" if not wrong else "wrong"), "wrong": wrong[:6], "collateral": coll[:6],
            "asked_too": bool(asked)}


# ---------------------------------------------------------------- prompts
SKILL_NOTES = """You are the ARRANGE lyric assistant. A composer sings their words on a melody they played on piano, and
looks at it on the SCORE CANVAS: the melody engraved as a score with bar numbers, the syllable under each note, and a
small grey number under each syllable. The sung line is a FIT: one row per note of the melody.
- bar and beat are as the canvas shows them: when the composer says "bar 18 beat 2" he means the row at bar 18, beat 2.
  Beats are the composer's beats (in 4/4, four per bar; in 3/4, three); 2.5 is halfway through beat 2.
- no. is the grey number the canvas prints under each sung syllable: it counts the syllables of a line from 1 (a new
  line starts after a gap of a second or more). "note 23" means the syllable with grey number 23.
- t and end are seconds in the piano recording.
- kind is "note" (carries a syllable in text), "slur" (holds the previous syllable over another note; text "~"), or
  "unsung" (a piano note the voice does not sing; text "").
- word groups the syllables of one word (rows with the same word share it); the singer gets each syllable as sounds
  (ARPAbet from the CMU dictionary), the word's sounds split between its notes at the vowels.
- The composer can set the sounds of a word in a PRONOUNCE file: {"Footsteps": ["F UH1", "T S EH1 P S"]} (one entry per
  note of the word). An entry applies to every place the word is sung.
- The composer writes notes as C4, Bb4, F#4 and often in shorthand: "walls (G4 F4)" = the word sung over G4 then F4.
- The composer owns every placement: change only what they ask for. If the request could mean more than one edit, or
  leaves out something the edit needs, ask one short question instead of guessing."""

OPS_DOC = """Answer ONLY with a JSON list of edits (no prose). Row numbers are the idx column as it is now; every edit refers
to these numbers, applied in order.
  {"op":"set","row":i, ...any of "text","kind","word","pitch" (e.g. "A4"),"t","end" (seconds)}
  {"op":"move","row":i,"bar":b,"beat":x}      start this note at the canvas bar/beat; it keeps its length unless you
                                              also give "end" (seconds)
  {"op":"shift","rows":[i,...],"by":s}        move these notes by s seconds (negative = earlier), start and end
  {"op":"insert","after":i,"pitch":"G4","kind":"note","text":"...","word":"...","t":s,"end":s}
  {"op":"delete","row":i}
  {"op":"pronounce","word":"Footsteps","sounds":["F UH1","T S EH1 P S"]}
  {"op":"ask","question":"..."}               if you cannot tell what the composer wants (then make no edits)
  {"op":"say","text":"..."}                   to answer the composer when he asks a question rather than for a change
                                              (then make no edits)"""

BARE_SYSTEM = "You are helping a composer edit the sung line (lyrics on a melody) of their song. The line is JSON."
BARE_DOC = """Answer ONLY with one JSON object (no prose, no code fences): {"rows": [<every row, edited>]}. Change only what
the composer asks. If the request is unclear or leaves out something you need, answer {"ask": "<one short question>"}
instead. If he asks a question rather than for a change, answer {"say": "<your answer>"}."""


def table(it):
    lines = ["idx | bar.beat | no. | t - end (s) | pitch | kind | text | word"]
    for i, r in enumerate(it["before"]):
        lines.append(f"{i} | {r['bar']}.{r['beat']:g} | {r['num'] or ''} | {r['t']:.3f} - {r['end']:.3f} | {L.nn(r['pitch'])} | {r['kind']} | {r['text']} | {r['word'] or ''}")
    return "\n".join(lines)


def raw_rows(it):
    return json.dumps([{k: r[k] for k in ("t", "end", "pitch", "bar", "beat", "text", "word", "kind")} for r in it["before"]], ensure_ascii=False)


def sounds_text(it):
    S = L.sounds([{k: v for k, v in r.items() if k in ("t", "end", "pitch", "text", "word", "kind")} for r in it["before"]], it["pron_before"], "new",
                 key=f"edit-{it['id']}-before")   # per item: items with earlier edits ('pre') have their own sounds
    return "\n".join(f"{t:.3f} {txt}: {ph}" for txt, ph, t in S)


def prompt(it, arm):
    req = (f"EARLIER IN THIS SESSION:\n{it['history']}\n\n" if it.get("history") else "") + f"THE COMPOSER SAYS: {it['request']}"
    if it.get("image_path"):
        req += "\n(He attached a screenshot of the score canvas; the red circles are his.)"
    if arm == "bare":
        return BARE_SYSTEM, f"ROWS:\n{raw_rows(it)}\n\n{req}\n\n{BARE_DOC}"
    info = (f"Song: {it['title']}, {it['ts']}.\n\nPRONOUNCE FILE: {json.dumps(it['pron_before'], ensure_ascii=False)}\n\n"
            f"SOUNDS THE SINGER GETS NOW (sung rows, start time, syllable: sounds):\n{sounds_text(it)}")
    return SKILL_NOTES, f"FIT:\n{table(it)}\n\n{info}\n\n{req}\n\n{OPS_DOC}"


# ---------------------------------------------------------------- model calls
def call(system, user, model, img):
    if R.BACKEND["kind"] == "openai":
        import base64, urllib.request
        content = [{"type": "text", "text": user}]
        if img:
            content.insert(0, {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(Path(img).read_bytes()).decode()}})
        body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}], "max_tokens": 16000, "temperature": 1.0}
        t0 = time.time()
        req = urllib.request.Request(R.BACKEND["base_url"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        j = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        txt = re.sub(r"<think>.*?</think>", "", j["choices"][0]["message"].get("content") or "", flags=re.S)
        return txt, {"total_cost_usd": 0.0}, round(time.time() - t0, 1)
    if not img:
        return R.call_model(system, user, model)
    cmd = ["claude", "-p", "--output-format", "json", "--model", model, "--no-session-persistence", "--system-prompt", system, "--tools", "Read", "--allowedTools", "Read"]
    # Read is the only tool: with the default tools a model can start a background file search that stalls the call.
    # The call runs in a fresh folder outside any project, so the CLI loads no project instructions or memory: the
    # same context as the calls without an image and the open models.
    import shutil, tempfile
    neutral = Path(tempfile.mkdtemp(prefix="edit-img-")); shutil.copy(img, neutral / Path(img).name)
    t0 = time.time()
    r = subprocess.run(cmd, input=f"First read the image file {Path(img).name} (the composer's screenshot).\n\n" + user,
                       capture_output=True, text=True, timeout=900, cwd=str(neutral))
    shutil.rmtree(neutral, ignore_errors=True)
    j = json.loads(r.stdout)
    return j.get("result", ""), {"total_cost_usd": j.get("total_cost_usd") or 0}, round(time.time() - t0, 1)


def one(it, arm, model, t_of):
    system, user = prompt(it, arm)
    text, usage, el = call(system, user, model, it.get("image_path"))
    if L.LIMIT.search(text[:300]) and not (usage or {}).get("total_cost_usd"):
        raise L.LimitHit(text[:200])
    try:
        obj = R.extract_json(text)
        if arm == "typed":
            obj = [obj] if isinstance(obj, dict) else obj
            rows, pron, asked = apply_ops(it, obj, t_of)
        elif isinstance(obj, dict) and ("ask" in obj or "say" in obj) and "rows" not in obj:
            rows, pron, asked = [dict(r) for r in it["before"]], it["pron_before"], [obj.get("ask") or obj.get("say")]
        else:
            rows, pron, asked = apply_rows(it, obj)
        s = score(it, rows, pron, asked)
        s["questions"] = asked
    except Exception as e:  # noqa: BLE001
        s = {"correct": False, "outcome": "invalid", "error": str(e)[:300]}
    return {"arm": arm, "score": s, "answer": text[:4000], "cost": (usage or {}).get("total_cost_usd", 0), "elapsed": el}


def clocks():
    """canvas clocks per song, computed once in the analysis venv and cached as a beat table."""
    cache = BUILD / "clocks.json"
    if not cache.exists():
        code = ("import json,sys; sys.path.insert(0,%r); from canvas_pos import canvas_clock; from items import ITEMS\n"
                "out={}\nfor s in sorted({i['song'] for i in ITEMS}):\n t=canvas_clock(%r+'/'+s); out[s]={f'{b}:{x}':t(b,x/4+1) for b in range(1,60) for x in range(0,24) if x/4+1<7}\n"
                "json.dump(out,open(%r,'w'))") % (str(HERE), str(RUNS), str(cache))
        subprocess.run([ANALYSIS_PY, "-c", code], check=True, cwd=str(HERE), capture_output=True)
    C = json.load(open(cache))

    def mk(song):
        def t_of(bar, beat):
            k = f"{bar}:{int(round((beat - 1) * 4))}"
            if k not in C[song]:
                raise ValueError(f"no canvas position {bar}.{beat}")
            return C[song][k]
        return t_of
    return {s: mk(s) for s in C}


# ---------------------------------------------------------------- selftest / run / table
def selftest():
    its = load(); bad = 0
    for it in its:
        if it["kind"] == "question":
            g = score(it, [dict(r) for r in it["before"]], it["pron_before"], [" ".join(it["say"])])
        elif it["gold"]:
            g = score(it, *gold_rows(it), [])
            for alt in it.get("alts", []):
                ga = score(it, *apply_ops(it, alt)[:2], [])
                g = g if ga["correct"] else {**ga, "correct": False}
        elif "check" in it:
            rows = [dict(r) for r in it["before"]]
            if "earlier" in it["check"]:
                c = it["check"]["earlier"]; rows[c["row"]]["t"] -= (c["min"] + c["max"]) / 2; rows[c["prev"]]["end"] = rows[c["row"]]["t"]
            else:
                c = it["check"]["gap_before"]; rows[c["prev"]]["end"] = rows[c["row"]]["t"] - (c["min"] + c["max"]) / 2
            g = score(it, rows, it["pron_before"], [])
        else:
            g = {"correct": None}
        n = score(it, [dict(r) for r in it["before"]], it["pron_before"], [])
        a = score(it, [dict(r) for r in it["before"]], it["pron_before"], ["?"])
        want_ask = "ask" in it.get("accept", ["gold"])
        ok = (g["correct"] in (True, None)) and not n["correct"] and a["correct"] == want_ask
        bad += not ok
        print(f"{it['id']:5s} {'complete' if it['complete'] else 'ASK     '} gold={g['correct']} {g.get('wrong', '')}{g.get('collateral', '')} | no-change={n['correct']} | ask={a['correct']}  {'' if ok else '<-- FAIL'}")
    print("selftest", "ok" if not bad else f"{bad} failing")


def run(a):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    its = load(); RES.mkdir(exist_ok=True); clk = clocks(); lock = threading.Lock()
    if a.only:
        its = [i for i in its if i["id"] in a.only]
    f = RES / f"{a.model}.json"
    res = json.load(open(f)) if f.exists() else {"model": a.model, "rows": {}}
    jobs = []
    for it in its:
        for arm in a.arms:
            have = res["rows"].setdefault(it["id"], {}).setdefault(arm, [])
            have[:] = [d for d in have if not L.LIMIT.search(d.get("answer", "")[:300])]
            jobs += [(it, arm)] * max(0, a.draws - len(have))

    def work(job):
        it, arm = job
        d = one(it, arm, a.model, clk[it["song"]])
        with lock:
            res["rows"][it["id"]][arm].append(d); json.dump(res, open(f, "w"), indent=1)
        print(f"{a.model} {it['id']} {arm}: {d['score']['outcome']} {d['elapsed']}s", flush=True)
    if a.workers <= 1:
        for j in jobs:
            work(j)
    else:
        with ThreadPoolExecutor(a.workers) as ex:
            list(ex.map(work, jobs))


def table_md():
    its = {i["id"]: i for i in load()}; K = ["single", "list", "pattern", "passage", "symptom", "revision", "question"]
    out = ["# E2-edits — curated edit requests on the score canvas", "",
           "| model | arm | correct | " + " | ".join(K) + " | incomplete: asked | complete: over-asked | screenshot | invalid | cost $ |",
           "|---|---|---|" + "---|" * len(K) + "---|---|---|---|---|"]
    for f in sorted(RES.glob("*.json")):
        res = json.load(open(f))
        for arm in ("typed", "bare"):
            D = [(its[i], d) for i, A in res["rows"].items() if i in its for d in A.get(arm, [])]
            if not D:
                continue
            def frac(sel):
                x = [d["score"]["correct"] for it, d in D if sel(it)]
                return f"{sum(x)}/{len(x)}" if x else "-"
            out.append(f"| {res['model']} | {arm} | {sum(d['score']['correct'] for _, d in D) / len(D):.2f} | "
                       + " | ".join(frac(lambda i, k=k: i["kind"] == k) for k in K)
                       + f" | {frac(lambda i: not i['complete'])} | {sum(d['score']['outcome'] == 'asked' for i, d in D if i['complete'])} | "
                       f"{frac(lambda i: 'image' in i['refs'])} | {sum(d['score']['outcome'] == 'invalid' for _, d in D)} | {sum(d.get('cost', 0) for _, d in D):.2f} |")
    (HERE / "TABLE.md").write_text("\n".join(out) + "\n"); print("\n".join(out))


def item_analysis():
    """Does the test tell conditions apart? Per item: pass rate pooled over every model and arm (difficulty, blind to
    which arm won), the spread across model x arm cells (discrimination) and try-to-try agreement (noise). Three tiers:
    'basic' = every cell passes, kept as unit tests (the skill and the edit format work at all; a skill
    change that breaks one is a regression), reported apart from the comparison; 'unsolved' = no cell passes, reviewed
    by the composer (a faulty request or answer, or a real limit); the rest measure (they separate models and arms). Tiers
    use the pooled result only, never the skill-minus-bare difference, so revising cannot inflate the skill's effect.
    Suite level: skill minus bare paired by item (sign test), and each model's pass rate with a 95% bootstrap interval."""
    import random
    random.seed(0)   # the bootstrap intervals are reproducible
    its = {i["id"]: i for i in load()}; cells = {}
    for f in sorted(RES.glob("*.json")):
        res = json.load(open(f))
        for iid, A in res["rows"].items():
            for arm, D in A.items():
                if iid in its and D:
                    cells.setdefault(iid, {})[(res["model"], arm)] = [bool(d["score"]["correct"]) for d in D]
    out = ["# E2-edits item analysis", "", "| item | kind | what | refs | complete | pooled | cells passing | cells mixed | tier |", "|---|---|---|---|---|---|---|---|---|"]
    for iid, C in cells.items():
        it = its[iid]; allx = [x for v in C.values() for x in v]; pooled = sum(allx) / len(allx)
        rates = [sum(v) / len(v) for v in C.values()]
        flag = "basic" if min(rates) == 1 else ("unsolved" if max(rates) == 0 else ("measures, noisy" if sum(0 < r < 1 for r in rates) > len(rates) / 2 else "measures"))
        out.append(f"| {iid} | {it['kind']} | {'+'.join(it['what'])} | {len(it['refs'])} {'+'.join(it['refs'])} | {'yes' if it['complete'] else 'ASK'} | {pooled:.2f} | "
                   f"{sum(r == 1 for r in rates)}/{len(rates)} | {sum(0 < r < 1 for r in rates)} | {flag} |")
    models = sorted({m for C in cells.values() for (m, _) in C})
    out += ["", "| model | typed | bare | typed - bare (items better/worse) | sign-test p |", "|---|---|---|---|---|"]
    from math import comb
    for m in models:
        rate = {}
        for arm in ("typed", "bare"):
            per = {i: sum(C[(m, arm)]) / len(C[(m, arm)]) for i, C in cells.items() if (m, arm) in C}
            ids = list(per); bs = []
            for _ in range(2000):
                smp = [random.choice(ids) for _ in ids]; bs.append(sum(per[i] for i in smp) / len(smp))
            bs.sort(); rate[arm] = (sum(per.values()) / len(per), bs[50], bs[1949], per)
        if "typed" in rate and "bare" in rate:
            T, Bp = rate["typed"][3], rate["bare"][3]; both = [i for i in T if i in Bp]
            up = sum(T[i] > Bp[i] for i in both); dn = sum(T[i] < Bp[i] for i in both); n = up + dn
            p = min(1.0, 2 * sum(comb(n, k) for k in range(min(up, dn) + 1)) / 2 ** n) if n else 1.0
            out.append(f"| {m} | {rate['typed'][0]:.2f} ({rate['typed'][1]:.2f}-{rate['typed'][2]:.2f}) | {rate['bare'][0]:.2f} ({rate['bare'][1]:.2f}-{rate['bare'][2]:.2f}) | "
                       f"{rate['typed'][0] - rate['bare'][0]:+.2f} ({up}/{dn}) | {p:.3g} |")
    (HERE / "ITEMS.md").write_text("\n".join(out) + "\n"); print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--table", action="store_true"); ap.add_argument("--items", action="store_true")
    ap.add_argument("--model"); ap.add_argument("--draws", type=int, default=3); ap.add_argument("--arms", nargs="*", default=["typed", "bare"])
    ap.add_argument("--only", nargs="*"); ap.add_argument("--base-url"); ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    if a.base_url:
        R.BACKEND.update(kind="openai", base_url=a.base_url)
    if a.build:
        build()
    elif a.selftest:
        selftest()
    elif a.table:
        table_md()
    elif a.items:
        item_analysis()
    elif a.model:
        run(a)
