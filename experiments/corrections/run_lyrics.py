#!/usr/bin/env python3
"""run_lyrics.py — E2-lyrics: the composer's real corrections to the sung layer (timing, fitting, phonemes, words),
carried out by a model with vs without the ARRANGE lyric skill's structure.

    python3 run_lyrics.py --model claude-haiku-5-5 [--draws 3] [--arms typed free bare] [--base-url URL]
    python3 run_lyrics.py --selftest      # gold answers must score correct with 0 collateral; 'no change' must fail
    python3 run_lyrics.py --table         # TABLE.md

Items: candidates.json minus the two dictation-format items (older format) and the open-ended writing item (scored by
constraints, not run here): the composer's exact words as the request, his actual fix as the gold.
Arms (same request, same fit):
  typed  ARRANGE notes (fit-format rules, bar numbers in the composer's count, the project's feel, the pronounce file and
         the sounds the singer gets now) + the fit as a numbered table; answer = a short list of row edits that the
         program applies (bar/beat -> seconds through the measured map).
  free   the same notes and information; the model returns the whole edited fit rows (and a pronounce file).
  bare   no notes: the raw fit rows JSON and the request; the model returns the whole edited rows.
Scoring is by outcome against the gold fit: model rows are aligned to gold rows (pitch + time); every change the request
asked for must be there (t within 0.05 s, end within 0.10 s; text, kind, word, pitch exact); rows the request did not
touch must be unchanged (collateral otherwise; changes the session itself also made unasked are allowed either way).
Phoneme items are scored on the sounds the singer gets (phonemes.py on the result + pronounce file), so a fix by
re-splitting the text counts as much as a pronounce entry.
"""
import argparse, copy, json, os, random, re, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "revisions"))
import run_e2 as R  # noqa: E402  (model call backends, JSON extraction)

SKIP = {"cp-dict-footsteps-pickup", "cp-dict-line3-rest", "atty-words-bars13-18"}
PY_G2P = os.environ.get("ARRANGE_G2P_PY", sys.executable)   # a Python with g2p_en
NOTE = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
CACHE = HERE / "cache"; CACHE.mkdir(exist_ok=True)


def nn(p):
    return f"{NOTE[p % 12]}{p // 12 - 1}" if isinstance(p, int) else str(p)


def to_midi(x):
    if isinstance(x, (int, float)):
        return int(x)
    m = re.match(r"^\s*([A-Ga-g])([#b♯♭]?)(-?\d)\s*$", str(x))
    if not m:
        raise ValueError(f"not a note: {x}")
    return {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1).upper()] + {"#": 1, "♯": 1, "b": -1, "♭": -1, "": 0}[m.group(2)] + 12 * (int(m.group(3)) + 1)


# ---------------------------------------------------------------- items
def items():
    spec = json.load(open(HERE / "candidates.json"))
    out = []
    for it in spec["items"]:
        if it["id"] in SKIP:
            continue
        d = HERE / "items" / it["id"]
        ctx = sorted(d.glob("context/piano-analysis*.json"))
        rec = {"id": it["id"], "cat": it["category"], "rec": it, "request": (d / "request.txt").read_text().strip(),
               "before": json.load(open(d / "before.json")), "after": json.load(open(d / "after.json")),
               "pron_before": json.load(open(d / "pronounce.before.json")) if (d / "pronounce.before.json").exists() else {},
               "pron_after": json.load(open(d / "pronounce.after.json")) if (d / "pronounce.after.json").exists() else None,
               "analysis": json.load(open(ctx[0])) if ctx else None,
               "phon": "old" if it["id"] == "cp-morning-sounds" else "new"}
        if rec["pron_after"] is None:
            rec["pron_after"] = rec["pron_before"]
        out.append(rec)
    return out


def sounds(rows, pron, ver, key=None):
    """phonemes.py (the version the gold was made with) on these rows + pronounce file -> list of (text, phoneme) per sung row."""
    if key and (CACHE / f"{key}.json").exists():
        return json.load(open(CACHE / f"{key}.json"))
    with tempfile.TemporaryDirectory() as td:
        fi, fo, fp = Path(td) / "fit.json", Path(td) / "score.json", Path(td) / "pron.json"
        json.dump({"rows": [{k: v for k, v in r.items() if k != "_o"} for r in rows]}, open(fi, "w")); json.dump(pron or {}, open(fp, "w"))
        r = subprocess.run([PY_G2P, str(HERE / f"phonemes/phonemes_{ver}.py"), str(fi), str(fo), "--pronounce", str(fp)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError(f"phonemes.py failed: {r.stderr[-300:]}")
        d = json.load(open(fo)); rs = d["rows"] if isinstance(d, dict) else d
        out = [[x.get("text"), x.get("phoneme"), round(float(x.get("t", 0)), 3)] for x in rs]
    if key:
        json.dump(out, open(CACHE / f"{key}.json", "w"))
    return out


# ---------------------------------------------------------------- prompts
SKILL_NOTES = """You are the ARRANGE lyric assistant. A composer sings their words on a melody they played on piano. The sung
line is a FIT: one row per note of the melody.
- t and end are seconds in the piano recording; bar and beat are read from the measured beat map (for reading). Bar numbers
  are the composer's own count: when the composer says "bar 18" they mean the rows with bar 18.
- kind is "note" (carries a syllable in text), "slur" (holds the previous syllable; text "~"), or "unsung" (a piano note the
  voice does not sing; text "").
- word groups the syllables of one word (rows with the same word share it); the singer gets each syllable as sounds
  (ARPAbet from the CMU dictionary), the word's sounds split between its notes at the vowels, consonants going to the
  next note as far as an English syllable can begin with them.
- The composer can set the split of a word's sounds across its notes in a PRONOUNCE file:
  {"Footsteps": ["F UH1", "T S EH1 P S"]} (one entry per note of the word, vowels with a stress digit; keys match any case).
- The composer owns every placement: change only what they ask for."""

OPS_DOC = """Answer ONLY with a JSON list of edits (no prose). Row numbers are the idx column as it is now; every edit refers
to these numbers, applied in order.
  {"op":"set","row":i, ...any of "text","kind","word","pitch" (e.g. "A4"),"t","end" (seconds)}
  {"op":"move","row":i,"bar":b,"beat":x}      start this note at bar/beat (beats as in the table); it keeps its length
                                              unless you also give "end" (seconds)
  {"op":"shift","rows":[i,...],"by":s}        move these notes by s seconds (negative = earlier), start and end
  {"op":"insert","after":i,"pitch":"G4","kind":"note","text":"...","word":"...","t":s,"end":s}
  {"op":"delete","row":i}
  {"op":"pronounce","word":"Footsteps","sounds":["F UH1","T S EH1 P S"]}
  {"op":"ask","question":"..."}               if you cannot tell what the composer wants"""

FREE_DOC = """Answer ONLY with one JSON object (no prose, no code fences): {"rows": [<every row of the fit, edited, with the
fields t, end, pitch, bar, beat, text, word, kind, placed>], "pronounce": {<the whole pronounce file after your change>}}.
Change only what the composer asks."""

BARE_SYSTEM = "You are helping a composer edit the sung line (lyrics on a melody) of their song. The line is JSON."
BARE_DOC = """Answer ONLY with one JSON object (no prose, no code fences): {"rows": [<every row, edited>]}.
Change only what the composer asks."""


def feel(an):
    if not an:
        return ""
    tm = an.get("tempo_map", {})
    hp = tm.get("his_per_beat")
    s = f"Feel: {tm.get('feel') or tm.get('notated_time_signature') or tm.get('time_signature')}."
    if hp and hp != 1:
        s += f" One beat of the map is {hp} of the composer's beats."
    return s


def table(rows):
    lines = ["idx | bar.beat | t - end (s) | note | kind | text | word"]
    for i, r in enumerate(rows):
        bb = f"{r.get('bar')}.{r.get('beat')}" if r.get("bar") is not None else "-"
        lines.append(f"{i} | {bb} | {r['t']:.3f} - {r['end']:.3f} | {nn(r['pitch'])} | {r.get('kind')} | {r.get('text')} | {r.get('word') or ''}")
    return "\n".join(lines)


def sounds_text(it):
    s = sounds(it["before"]["rows"], it["pron_before"], it["phon"], key=f"{it['id']}-before")
    return "\n".join(f"{t:.3f} {txt}: {ph}" for txt, ph, t in s)


def raw_rows(rows):
    keep = ("t", "end", "pitch", "bar", "beat", "text", "word", "kind", "placed")
    return json.dumps([{k: r.get(k) for k in keep if k in r} for r in rows], ensure_ascii=False)


def prompt(it, arm):
    rows = it["before"]["rows"]; req = it["request"]
    if arm == "bare":
        return BARE_SYSTEM, f"ROWS:\n{raw_rows(rows)}\n\nTHE COMPOSER SAYS: {req}\n\n{BARE_DOC}"
    info = (f"{feel(it['analysis'])}\n\nPRONOUNCE FILE: {json.dumps(it['pron_before'], ensure_ascii=False)}\n\n"
            f"SOUNDS THE SINGER GETS NOW (sung rows, start time, syllable: sounds):\n{sounds_text(it)}")
    if arm == "typed":
        return SKILL_NOTES, f"FIT:\n{table(rows)}\n\n{info}\n\nTHE COMPOSER SAYS: {req}\n\n{OPS_DOC}"
    return SKILL_NOTES, f"FIT ROWS:\n{raw_rows(rows)}\n\nTHE SAME ROWS AS A TABLE:\n{table(rows)}\n\n{info}\n\nTHE COMPOSER SAYS: {req}\n\n{FREE_DOC}"


# ---------------------------------------------------------------- applying answers
def clock(an):
    beats = an["tempo_map"]["beats"]

    def t_of(bar, beat):
        bar, beat = int(bar), float(beat); b0 = int(beat)
        for k, e in enumerate(beats):
            if e["bar"] == bar and int(e["beat"]) == b0:
                nxt = beats[k + 1]["t"] if k + 1 < len(beats) else e["t"] + (e["t"] - beats[k - 1]["t"])
                return e["t"] + (beat - b0) * (nxt - e["t"])
        raise ValueError(f"no beat {bar}.{beat} in the map")
    return t_of


def apply_typed(it, ops):
    rows = [dict(r, _o=i) for i, r in enumerate(copy.deepcopy(it["before"]["rows"]))]
    pron = copy.deepcopy(it["pron_before"]); asked = []
    t_of = clock(it["analysis"]) if it["analysis"] else None

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
            if "pitch" in op:
                r["pitch"] = to_midi(op["pitch"])
        elif o == "move":
            r = find(op["row"]); d = r["end"] - r["t"]
            if t_of is None:
                raise ValueError("no beat map for move")
            r["t"] = t_of(op["bar"], op["beat"]); r["bar"], r["beat"] = int(op["bar"]), float(op["beat"])
            r["end"] = float(op["end"]) if "end" in op else r["t"] + d
        elif o == "shift":
            for i in op["rows"]:
                r = find(i); r["t"] += float(op["by"]); r["end"] += float(op["by"])
        elif o == "insert":
            r = find(op["after"]); new = {"t": float(op["t"]), "end": float(op["end"]), "pitch": to_midi(op["pitch"]), "kind": op.get("kind", "note"),
                                           "text": op.get("text", ""), "word": op.get("word"), "placed": "inserted", "bar": None, "beat": None}
            rows.insert(rows.index(r) + 1, new)
        elif o == "delete":
            rows.remove(find(op["row"]))
        elif o == "pronounce":
            pron[op["word"]] = op["sounds"]
        elif o == "ask":
            asked.append(op.get("question"))
        else:
            raise ValueError(f"unknown op {o}")
    for r in rows:
        r.pop("_o", None)
    return rows, pron, asked


def apply_rewrite(obj, it, arm):
    rows = obj["rows"]
    for r in rows:
        r["pitch"] = to_midi(r["pitch"]); r["t"] = float(r["t"]); r["end"] = float(r["end"])
    pron = obj.get("pronounce", it["pron_before"]) if arm == "free" else it["pron_before"]
    return rows, pron or {}, []


# ---------------------------------------------------------------- scoring
def norm_text(r):
    k = r.get("kind"); t = (r.get("text") or "").strip().lower()
    return "~" if k == "slur" else ("" if k == "unsung" else t)


def same(r, g, tt, te, word=True):
    if r.get("kind") != g.get("kind") or to_midi(r["pitch"]) != g["pitch"] or norm_text(r) != norm_text(g):
        return False
    if word and g.get("kind") != "unsung" and (r.get("word") or "").strip().lower() != (g.get("word") or "").strip().lower():
        return False
    return abs(r["t"] - g["t"]) <= tt and abs(r["end"] - g["end"]) <= te


def align(A, B, win=0.5):
    """Order-preserving alignment of rows A to rows B: pairs with the same pitch within win seconds, closest first."""
    n, m = len(A), len(B)
    S = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            best = max(S[i + 1][j], S[i][j + 1])
            if to_midi(A[i]["pitch"]) == B[j]["pitch"] and abs(A[i]["t"] - B[j]["t"]) < win:
                best = max(best, 1 + (win - abs(A[i]["t"] - B[j]["t"])) / (10 * win) + S[i + 1][j + 1])
            S[i][j] = best
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if to_midi(A[i]["pitch"]) == B[j]["pitch"] and abs(A[i]["t"] - B[j]["t"]) < win and \
                abs(S[i][j] - (1 + (win - abs(A[i]["t"] - B[j]["t"])) / (10 * win) + S[i + 1][j + 1])) < 1e-9:
            pairs.append((i, j)); i += 1; j += 1
        elif S[i + 1][j] >= S[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


TT = {"cp-layer-pitches": 0.30}   # time tolerances from each record


def stress(ph):
    return re.sub(r"2", "1", ph or "")


def alt_golds(it):
    """Answers the record lists as equally faithful (acceptable_alternatives), as alternative gold rows."""
    G = it["after"]["rows"]
    if it["id"] == "sd-hall-g4":   # G4 as a hold of 'hall' instead of the word 'hallway'
        A = copy.deepcopy(G)
        for r in A:
            if (r.get("text") or "").lower() == "way" and r["pitch"] == 67:
                r.update(kind="slur", text="~", word="hall")
            if (r.get("text") or "").lower() == "hall":
                r["word"] = "hall"
        return [A]
    return []


def custom(it, rows, Sm):
    """Item-specific acceptance from the record's tolerance text; returns None when the item has no custom rule."""
    if it["id"] == "cp-layer-words":   # every syllable its own note, the new words in order, nothing else moved
        syl = lambda L: [norm_text(r) for r in L if r.get("kind") == "note"]
        return syl(rows) == syl(it["after"]["rows"])
    if it["id"] == "cp-footsteps-sounds" and Sm is not None:   # one T across the two notes, no stop cluster at the join
        fs = [ph for txt, ph, _ in Sm if (txt or "").lower() in ("foot", "steps")]
        return len(fs) == 2 and sum(ph.replace("en_", "").split("-").count("T") for ph in fs) == 1
    return None


def score(it, rows, pron):
    s = score_one(it, rows, pron, strict=True)
    acc = score_one(it, rows, pron, strict=False)
    for alt in alt_golds(it):
        a2 = score_one(dict(it, after={"rows": alt}), rows, pron, strict=False)
        if a2["correct"]:
            acc = a2
    c = custom(it, rows, acc.get("_Sm"))
    if c is not None and it["cat"] in ("phoneme",):
        acc["correct"] = acc["request_done"] = bool(c) and not [x for x in acc["collateral"] if not x.startswith("sound")]
    elif c is not None:
        acc["correct"] = acc["request_done"] = bool(c) and acc["n_collateral"] == 0
    acc.pop("_Sm", None); s.pop("_Sm", None)
    return {"correct": acc["correct"], "request_done": acc["request_done"], "strict_correct": s["correct"],
            "missing": acc["missing"], "wrong": acc["wrong"], "collateral": acc["collateral"], "n_collateral": acc["n_collateral"],
            "strict_wrong": s["wrong"][:6]}


def score_one(it, rows, pron, strict=True):
    G, B = it["after"]["rows"], it["before"]["rows"]
    tt = 0.05 if strict else TT.get(it["id"], 0.05)
    gold, other = it["rec"]["gold"].get("row_changes") or [], it["rec"]["other_changes_same_edit"] or []
    req = {c["after_row"] for c in gold if c["op"] in ("modify", "insert")}
    allowed = {c["after_row"] for c in other if c["op"] in ("modify", "insert")}
    req_del = [B[c["before_row"]] for c in gold if c["op"] == "delete"]
    ok_del = [B[c["before_row"]] for c in other if c["op"] == "delete"]
    pairs = align(rows, G); rm = {i for i, _ in pairs}; gm = {j: i for i, j in pairs}
    missing_req, wrong_req, collateral = [], [], []
    for j, g in enumerate(G):
        if j not in gm:
            (missing_req if j in req else ([] if j in allowed else collateral)).append(f"missing gold row {j} {nn(g['pitch'])} '{g.get('text')}' @{g['t']:.2f}")
            continue
        r = rows[gm[j]]
        if j in req:
            if not same(r, g, tt, 0.10 if strict else max(0.10, tt), word=strict):
                wrong_req.append(f"row {j} '{g.get('text')}' {nn(g['pitch'])}: got t {r['t']:.3f} end {r['end']:.3f} '{r.get('text')}' {r.get('kind')} w={r.get('word')}; want t {g['t']:.3f} end {g['end']:.3f} '{g.get('text')}' {g.get('kind')} w={g.get('word')}")
        elif j not in allowed and not same(r, g, 0.02, 0.02, word=strict):
            collateral.append(f"changed row {j} '{g.get('text')}' {nn(g['pitch'])} @{g['t']:.2f} -> '{r.get('text')}' {r.get('kind')} t {r['t']:.3f}-{r['end']:.3f} w={r.get('word')}")
    for i, r in enumerate(rows):
        if i in rm:
            continue
        near = lambda L: any(to_midi(r["pitch"]) == b["pitch"] and abs(r["t"] - b["t"]) < 0.06 for b in L)
        if near(req_del):
            missing_req.append(f"not deleted {nn(to_midi(r['pitch']))} '{r.get('text')}' @{r['t']:.2f}")
        elif not near(ok_del):
            collateral.append(f"extra row {nn(to_midi(r['pitch']))} '{r.get('text')}' @{r['t']:.2f}")
    snd = None; Sm = None
    if it["cat"] == "phoneme":
        Sb = sounds(B, it["pron_before"], it["phon"], key=f"{it['id']}-before"); Sa = sounds(G, it["pron_after"], it["phon"], key=f"{it['id']}-after")
        Sm = sounds(rows, pron, it["phon"])
        target = [k for k in range(len(Sa)) if Sa[k][1] != Sb[k][1]]
        side = []
        if len(Sm) != len(Sa):
            snd = {"ok": False, "why": f"{len(Sm)} sung rows, gold {len(Sa)}"}
        else:
            eq = (lambda x, y: x == y) if strict else (lambda x, y: stress(x) == stress(y))
            bad = [f"{Sa[k][0]}: got {Sm[k][1]} want {Sa[k][1]}" for k in target if not eq(Sm[k][1], Sa[k][1])]
            coll = [f"{Sb[k][0]}: {Sb[k][1]} -> {Sm[k][1]}" for k in range(len(Sa)) if k not in target and k not in side and not eq(Sm[k][1], Sb[k][1])]
            snd = {"ok": not bad and not coll, "wrong": bad, "collateral": coll}
            collateral += [f"sound {c}" for c in coll]
            wrong_req += [f"sound {b}" for b in bad]
    done = not missing_req and not wrong_req
    if it["cat"] == "phoneme":
        done = bool(snd and snd.get("ok") is True) and not missing_req
    return {"correct": done and not collateral, "request_done": done, "missing": missing_req, "wrong": wrong_req, "collateral": collateral,
            "n_collateral": len(collateral), "_Sm": Sm if it["cat"] == "phoneme" else None}


# ---------------------------------------------------------------- run
LIMIT = re.compile(r"hit your .{0,20}limit|reached your .{0,30}limit", re.I)


class LimitHit(Exception):
    pass


def one(it, arm, model):
    system, user = prompt(it, arm)
    text, usage, el = R.call_model(system, user, model)
    if LIMIT.search(text[:300]) and not (usage or {}).get("total_cost_usd"):
        raise LimitHit(text[:200])
    try:
        obj = R.extract_json(text)
        if arm == "typed":
            obj = [obj] if isinstance(obj, dict) else obj
            rows, pron, asked = apply_typed(it, obj)
        else:
            rows, pron, asked = apply_rewrite(obj, it, arm)
        s = score(it, rows, pron); outcome = "asked" if asked and not s["request_done"] else ("correct" if s["correct"] else "wrong")
    except Exception as e:
        s, outcome = {"correct": False, "request_done": False, "error": str(e)[:300], "n_collateral": 0}, "invalid"
    return {"outcome": outcome, "score": s, "raw": text[:60000], "usage": usage, "elapsed": round(el, 1)}


def selftest():
    for it in items():
        g = score(it, copy.deepcopy(it["after"]["rows"]), it["pron_after"])
        n = score(it, copy.deepcopy(it["before"]["rows"]), it["pron_before"])
        print(f"{it['id']:<22} {it['cat']:<8} gold: correct={g['correct']} coll={g['n_collateral']} {g['missing'][:1]}{g['wrong'][:1]}{g['collateral'][:2]} | "
              f"no-change: correct={n['correct']} done={n['request_done']}")


def table_md():
    n_items = len({r["id"] for f in (HERE / "results").glob("*.json") for r in json.load(open(f))["rows"]})
    lines = [f"# E2-lyrics — the composer's real corrections to the sung line ({n_items} items x 3 draws)", "",
             "| model | arm | accepted | strict (exactly his fix) | request done | collateral rows / draw | invalid | asked | timing | fitting | phoneme | words | cost $ |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in sorted((HERE / "results").glob("*.json")):
        res = json.load(open(f))
        for arm in ("typed", "free", "bare"):
            D = [d for r in res["rows"] for d in r["draws"].get(arm, [])]
            if not D:
                continue
            cats = {c: [d for r in res["rows"] if r["cat"] == c for d in r["draws"].get(arm, [])] for c in ("timing", "fitting", "phoneme", "words")}
            pc = lambda L: f"{sum(d['score']['correct'] for d in L)}/{len(L)}" if L else "-"
            cost = sum((d.get("usage") or {}).get("total_cost_usd") or 0 for d in D)
            lines.append(f"| {res['model']} | {arm} | {sum(d['score']['correct'] for d in D) / len(D):.2f} | {sum(d['score'].get('strict_correct', False) for d in D) / len(D):.2f} | {sum(d['score']['request_done'] for d in D) / len(D):.2f} | "
                         f"{sum(d['score'].get('n_collateral', 0) for d in D) / len(D):.1f} | {sum(d['outcome'] == 'invalid' for d in D)} | {sum(d['outcome'] == 'asked' for d in D)} | "
                         f"{pc(cats['timing'])} | {pc(cats['fitting'])} | {pc(cats['phoneme'])} | {pc(cats['words'])} | {cost:.2f} |")
    (HERE / "TABLE.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--draws", type=int, default=3); ap.add_argument("--arms", nargs="*", default=["typed", "free", "bare"])
    ap.add_argument("--base-url"); ap.add_argument("--only", nargs="*"); ap.add_argument("--selftest", action="store_true"); ap.add_argument("--table", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.table:
        return table_md()
    if a.base_url:
        R.BACKEND.update(kind="openai", base_url=a.base_url)
    out = HERE / "results" / f"{a.model}.json"; out.parent.mkdir(exist_ok=True)
    res = json.load(open(out)) if out.exists() else {"model": a.model, "rows": []}
    for r in res["rows"]:   # drop answers that were the account's usage-limit message, not the model's
        for arm in list(r["draws"]):
            r["draws"][arm] = [d for d in r["draws"][arm] if not LIMIT.search(d.get("raw", "")[:300])]
    byid = {r["id"]: r for r in res["rows"]}
    its = [it for it in items() if not a.only or it["id"] in a.only]
    for it in its:
        sounds_text(it)   # warm the cache before threads
    import concurrent.futures as cf
    jobs = []
    for it in its:
        rec = byid.setdefault(it["id"], {"id": it["id"], "cat": it["cat"], "draws": {}})
        for arm in a.arms:
            have = len(rec["draws"].get(arm, []))
            jobs += [(it, arm) for _ in range(max(0, a.draws - have))]
    if it_list := [r for r in byid.values() if r not in res["rows"]]:
        res["rows"] += it_list
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(one, it, arm, a.model): (it, arm) for it, arm in jobs}
        for f in cf.as_completed(futs):
            it, arm = futs[f]
            try:
                d = f.result()
            except LimitHit as e:
                print("usage limit hit, stopping:", e, flush=True); ex.shutdown(cancel_futures=True); break
            byid[it["id"]]["draws"].setdefault(arm, []).append(d)
            print(f"{a.model} {it['id']} {arm}: {d['outcome']} coll {d['score'].get('n_collateral')} {d['elapsed']}s", flush=True)
            out.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
