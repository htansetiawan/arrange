#!/usr/bin/env python3
"""notebook.py — parse ARRANGEMENT.md into notebook.json (tolerant, never fails).

    python3 notebook.py parse ARRANGEMENT.md -o notebook.json
    python3 notebook.py show  ARRANGEMENT.md            # human-readable dump

Contract: references/notebook-format.md. Everything the creator wrote is kept:
each cell carries its complete source text in `raw`, every component carries
the character span it came from (`chars`), and every piece of prose, including
prose on the same line as a component, is kept in order in `note`. Anything
unclassified becomes type "unknown" for /arrange-plan to ask about. Bars are the
only numbers here; nothing is converted to seconds.
"""
import argparse, json, re, sys
from pathlib import Path

TYPE_WORDS = {
    "vocal": ("vocal", "vocals", "voice", "sing", "singer", "lead"),
    "backing": ("backing", "harmony", "harmonies", "choir", "oohs", "aahs"),
    "lyrics": ("lyrics", "lyric", "words"),
    "strings": ("strings", "string", "violin", "violins", "viola", "violas", "cello", "cellos"),
    "pad": ("pad", "synth", "texture", "drone", "synthpad", "pads"),
    "guitar": ("guitar", "nylon", "acoustic", "electric"),
    "bass": ("bass", "upright", "sub"),
    "keys": ("keys", "rhodes", "organ", "celesta", "piano2", "second piano", "ep"),
    "drums": ("drums", "drum", "kit", "brushes"),
    "percussion": ("percussion", "perc", "shaker", "taiko", "hand drums"),
    "brass": ("brass", "horns", "horn", "trumpet", "trombone", "tuba"),
    "woodwinds": ("woodwinds", "woodwind", "flute", "clarinet", "oboe", "bassoon"),
    "fx": ("fx", "riser", "reverse", "ambience", "room", "swoosh"),
}
CLASS_OF = {
    "vocal": "vocals", "backing": "backing vocals", "strings": "strings", "pad": "synth",
    "guitar": "guitar", "bass": "bass", "keys": "keyboard", "drums": "drums",
    "percussion": "percussion", "brass": "brass", "woodwinds": "woodwinds", "fx": "fx",
}

HEAD_RE = re.compile(r"^##\s+(.*?)\s*$")
BARS_IN_HEAD_RE = re.compile(r"\(\s*bars?\s*(\d+)\s*[–\-]\s*(\d+)\s*\)", re.I)
VARIANT_RE = re.compile(r"\(\s*variant\s+([A-Za-z0-9]+)\s*\)", re.I)
ENTER_RE = re.compile(r"@\s*bar\s*(\d+)(?::(\d+))?", re.I)
SPAN_RE = re.compile(r"~\s*bars?\s*(\d+)\s*[–\-]\s*(\d+)", re.I)


def classify(body: str):
    head = body.split(":", 1)[0].strip().lower() if ":" in body else body.strip().lower()
    first = head.split()[0] if head.split() else ""
    for t, words in TYPE_WORDS.items():
        if first in words or head in words:
            return t
    for t, words in TYPE_WORDS.items():
        if any(w in head.split() for w in words):
            return t
    return "unknown"


def parse_component(raw: str, chars=None, line=None):
    body = raw.strip()[1:-1].strip()  # drop < >
    decision = "claude"
    if body.endswith("!"):
        decision, body = "creator", body[:-1].rstrip()
    elif body.endswith("?"):
        decision, body = "tentative", body[:-1].rstrip()
    t = classify(body)
    comp = {"type": t, "class": CLASS_OF.get(t), "decision": decision, "raw": raw.strip()}
    if chars is not None:
        comp["chars"] = list(chars)
    if line is not None:
        comp["line"] = line
    text = body.split(":", 1)[1].strip() if ":" in body else body
    if t == "lyrics":
        comp["lines"] = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return comp
    m = ENTER_RE.search(text)
    comp["enter"] = {"bar": int(m.group(1)), "beat": int(m.group(2) or 1)} if m else None
    m2 = SPAN_RE.search(text)
    comp["span"] = {"bar_start": int(m2.group(1)), "bar_end": int(m2.group(2))} if m2 else None
    text = ENTER_RE.sub("", SPAN_RE.sub("", text)).strip()
    comp["text"] = re.sub(r"\s+", " ", text)
    return comp


def split_cell(raw: str):
    """Walk a cell's source once. Returns (components, prose_segments).

    Components are `<...>` runs (nesting-aware, multi-line). Everything else is
    prose and is kept, in order, with its character span. An unterminated `<`
    becomes an unknown component so nothing disappears.
    """
    comps, prose = [], []
    i, n = 0, len(raw)
    line_of = lambda k: raw.count("\n", 0, k) + 1
    while i < n:
        if raw[i] == "<":
            depth, j = 0, i
            while j < n:
                if raw[j] == "<":
                    depth += 1
                elif raw[j] == ">":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j < n:
                comps.append(parse_component(raw[i:j + 1], (i, j + 1), line_of(i)))
                i = j + 1
            else:
                comps.append({"type": "unknown", "class": None, "decision": "claude",
                              "raw": raw[i:].strip(), "text": raw[i + 1:].strip(),
                              "chars": [i, n], "line": line_of(i), "note": "unterminated <"})
                i = n
        else:
            j = raw.find("<", i)
            j = n if j == -1 else j
            prose.append({"chars": [i, j], "text": raw[i:j]})
            i = j
    return comps, prose


def tidy_note(segments):
    text = "".join(s["text"] for s in segments)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln); blank = False
        elif not blank and out:
            out.append(""); blank = True
    return "\n".join(out).strip()


def parse(md: str):
    front, body = {}, md
    if md.startswith("---"):
        parts = md.split("---", 2)
        if len(parts) >= 3:
            for ln in parts[1].splitlines():
                if ":" in ln and not ln.strip().startswith("#"):
                    k, v = ln.split(":", 1)
                    front[k.strip()] = v.split("#", 1)[0].strip()
            body = parts[2]
    cells, cur = [], None
    for lineno, line in enumerate(body.splitlines(keepends=True), 1):
        h = HEAD_RE.match(line.rstrip("\n"))
        if h:
            name = h.group(1)
            bars = BARS_IN_HEAD_RE.search(name)
            var = VARIANT_RE.search(name)
            clean = VARIANT_RE.sub("", BARS_IN_HEAD_RE.sub("", name)).strip()
            cur = {"name": clean, "bars": [int(bars.group(1)), int(bars.group(2))] if bars else None,
                   "variant": var.group(1) if var else None, "heading": line.rstrip("\n"),
                   "line": lineno, "raw": ""}
            cells.append(cur)
            continue
        if cur is None:
            if not line.strip():
                continue
            cur = {"name": "(untitled)", "bars": None, "variant": None, "heading": None, "line": lineno, "raw": ""}
            cells.append(cur)
        cur["raw"] += line
    for c in cells:
        comps, prose = split_cell(c["raw"])
        c["components"] = comps
        c["prose"] = [p for p in prose if p["text"].strip()]
        c["note"] = tidy_note(prose)
    return {"piece": front.get("piece"), "front": front, "cells": cells, "source_chars": len(md)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["parse", "show"])
    ap.add_argument("notebook")
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    nb = parse(Path(a.notebook).read_text(encoding="utf-8"))
    if a.cmd == "parse":
        out = json.dumps(nb, indent=2, ensure_ascii=False)
        Path(a.out).write_text(out, encoding="utf-8") if a.out else print(out)
        unknown = [(c["name"], k["raw"]) for c in nb["cells"] for k in c["components"] if k["type"] == "unknown"]
        if unknown:
            print(f"ASK-THE-CREATOR: {len(unknown)} unclassified component(s):", file=sys.stderr)
            for cell, raw in unknown:
                print(f"  [{cell}] {raw}", file=sys.stderr)
    else:
        for c in nb["cells"]:
            bars = f" bars {c['bars'][0]}–{c['bars'][1]}" if c["bars"] else ""
            var = f" (variant {c['variant']})" if c["variant"] else ""
            print(f"## {c['name']}{var}{bars}")
            if c["note"]:
                for ln in c["note"].splitlines():
                    print(f"   note: {ln}")
            for k in c["components"]:
                where = ""
                if k.get("enter"):
                    where += f" @bar {k['enter']['bar']}:{k['enter']['beat']}"
                if k.get("span"):
                    where += f" ~bars {k['span']['bar_start']}–{k['span']['bar_end']}"
                mark = {"creator": " !", "tentative": " ?"}.get(k["decision"], "")
                if k["type"] == "lyrics":
                    print(f"   - lyrics ({len(k['lines'])} lines)")
                else:
                    print(f"   - {k['type']:<10} [{k['class']}]{where}{mark}: {k.get('text','')}")


if __name__ == "__main__":
    main()
