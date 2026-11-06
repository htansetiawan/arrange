#!/usr/bin/env python3
"""bind.py — turn notebook components into layer drafts.

    python3 bind.py bind notebook.json piano-analysis.json [asset-catalog.json] -o bindings.json [--variant "chorus=B"]

Every component becomes exactly one layer draft: a generation job (audio route
for instruments, score route for voices), the creator's take when the text
asks for one and the catalogue has it, or a silent stub with a reason. Loose
input never fails: anything unclear is bound to the most literal reading and
listed under `questions` for the creator. Anchors are bar:beat; exits are
half-open (a component "through bar 40" exits at 41:1). Nothing here is
converted to seconds; build.py does that through clock.py.
"""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrangement as A  # noqa: E402

TAKE_WORDS = re.compile(r"\b(my (own )?(take|recording|recorded|part)|i recorded|use my|the take)\b", re.I)
STUB_WORDS = re.compile(r"\b(placeholder|empty track|stub|nothing decided|leave (it )?empty|silent for now)\b", re.I)


def choose_cells(nb, variant_choices):
    """One cell per section: the chosen variant, else the first; the rest become a question."""
    chosen, questions, seen = [], [], {}
    for c in nb["cells"]:
        key = c["name"].lower()
        if c.get("variant"):
            want = variant_choices.get(key)
            group = seen.setdefault(key, [])
            group.append(c)
            if want:
                if c["variant"].upper() == want.upper():
                    chosen.append(c)
            elif len(group) == 1:
                chosen.append(c)
        else:
            chosen.append(c)
    for key, group in seen.items():
        if len(group) > 1 and key not in variant_choices:
            vs = ", ".join(g["variant"] for g in group)
            questions.append(f"{group[0]['name']}: variants {vs} exist; variant {group[0]['variant']} is bound for now. Which one?")
    return chosen, questions


def section_bars(cell, analysis, questions):
    secs = {s["label"].lower(): s for s in analysis.get("sections", [])}
    s = secs.get(cell["name"].lower())
    if cell.get("bars") and s and [s["bar_start"], s["bar_end"]] != cell["bars"]:
        questions.append(f"{cell['name']}: the notebook says bars {cell['bars'][0]}–{cell['bars'][1]}, the analysis proposed {s['bar_start']}–{s['bar_end']}; the notebook's range is used.")
    if cell.get("bars"):
        return cell["bars"]
    if s:
        return [s["bar_start"], s["bar_end"]]
    questions.append(f"{cell['name']}: no bar range in the notebook and no section of that name in the analysis; the whole piece is assumed.")
    beats = analysis["tempo_map"]["beats"]
    return [beats[0]["bar"], beats[-1]["bar"]]


def bind(nb, analysis, catalog=None, variant_choices=None):
    variant_choices = {k.lower(): v for k, v in (variant_choices or {}).items()}
    analysis = dict(analysis); analysis["vibe"] = nb.get("front", {}).get("vibe", "")
    cells, questions = choose_cells(nb, variant_choices)
    drafts, n = [], 0
    assets = {a["id"]: a for a in (catalog or {}).get("assets", [])}
    for cell in cells:
        b0, b1 = section_bars(cell, analysis, questions)
        comps = cell["components"]
        lyrics = [c for c in comps if c["type"] == "lyrics"]
        vocal_present = any(c["type"] in ("vocal", "backing") for c in comps)
        if lyrics and not vocal_present:
            questions.append(f"{cell['name']}: lyrics without a vocal component; a default sung layer was added from the front matter's singer.")
            comps = comps + [{"type": "vocal", "class": "vocals", "decision": "claude", "raw": "<vocal: (default from lyrics)>",
                              "text": nb.get("front", {}).get("singer", "sung line"), "enter": None, "span": None, "chars": None}]
        for ci, c in enumerate(comps):
            if c["type"] == "lyrics":
                continue
            n += 1
            lid = f"L{n}"
            decision = c.get("decision", "claude")
            enter = {"bar": c["enter"]["bar"], "beat": float(c["enter"]["beat"])} if c.get("enter") else {"bar": b0, "beat": 1.0}
            if c.get("span"):
                enter = {"bar": c["span"]["bar_start"], "beat": 1.0} if not c.get("enter") else enter
                exit_ = {"bar": c["span"]["bar_end"] + 1, "beat": 1.0}
            else:
                exit_ = {"bar": b1 + 1, "beat": 1.0}
            if not (b0 <= enter["bar"] <= b1):
                questions.append(f"{cell['name']}: {c['raw']} enters at bar {enter['bar']}, outside bars {b0}–{b1}; bound as written.")
            cls = c.get("class")
            text = c.get("text", "")
            name = c["type"]
            if c["type"] == "unknown" or cls is None:
                L = A.new_layer(lid, (text.split(":")[0] or "unknown")[:24], None, text, enter, exit_, "stub",
                                from_={"cell": cell["name"], "component": ci, "raw": c["raw"], "chars": c.get("chars")}, analysis=analysis, decision=decision)
                L["stub_reason"] = "the notebook component could not be classified; ask the creator what it is"
                questions.append(f"{cell['name']}: could not tell what {c['raw']} is; it is a silent placeholder until you say.")
            elif STUB_WORDS.search(text):
                L = A.new_layer(lid, name, cls, text, enter, exit_, "stub",
                                from_={"cell": cell["name"], "component": ci, "raw": c["raw"], "chars": c.get("chars")}, analysis=analysis, decision=decision)
                L["stub_reason"] = "the notebook asks for a placeholder: " + text[:80]
                # a placeholder for a known class remembers the job it would run, so "put it back in" (unstub) works
                job = A.new_layer(lid, name, cls, text, enter, exit_, "score" if cls in ("vocals", "backing vocals") else "audio", analysis=analysis)
                L["before_stub"] = {"kind": "generated", "route": job["route"], "job": job["job"]}
            else:
                route = "score" if cls in ("vocals", "backing vocals") else "audio"
                asset = None
                if TAKE_WORDS.search(text):
                    cands = [a for a in assets.values() if a.get("class") == cls]
                    if cands:
                        route, asset = "take", cands[0]["id"]
                    else:
                        questions.append(f"{cell['name']}: {c['raw']} asks for your own take but the catalogue has no {cls} take; a generated {cls} is bound instead.")
                L = A.new_layer(lid, name, cls, text, enter, exit_, route,
                                from_={"cell": cell["name"], "component": ci, "raw": c["raw"], "chars": c.get("chars")}, analysis=analysis, decision=decision)
                if route == "take":
                    L["asset"] = asset; L["job"] = {"backend": "take", "inputs": {"asset": asset}}
                    L["owner"]["route"] = "creator"
                if route == "score" and lyrics:
                    L["lyrics"] = [ln for ly in lyrics for ln in ly["lines"]]
                if decision == "tentative":
                    questions.append(f"{cell['name']}: {c['raw']} is marked tentative; bound as {route}, say the word to drop or change it.")
            L["notes"] = cell.get("note", "")
            drafts.append(L)
    # order: vocals, then sustained, then rhythmic, then stubs; stable within a group
    def rank(L):
        if L["kind"] == "stub":
            return 3
        if L["class"] in ("vocals", "backing vocals"):
            return 0
        if L["class"] in A.RHYTHMIC:
            return 2
        return 1
    drafts.sort(key=rank)
    for i, L in enumerate(drafts, 1):   # ids follow the render order so the page reads top to bottom
        L["id"] = f"L{i}"
        if L.get("job") and L["job"].get("inputs"):
            L["job"]["inputs"] = {k: v.replace(f"jobs/L", f"jobs/L").replace(v.split("/")[1] if v.startswith("jobs/") else "", L["id"]) if isinstance(v, str) and v.startswith("jobs/") else v for k, v in L["job"]["inputs"].items()}
    return {"layers": drafts, "order": [L["id"] for L in drafts], "questions": questions,
            "cells": [{"name": c["name"], "variant": c.get("variant"), "bars": section_bars(c, analysis, [])} for c in cells]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["bind"])
    ap.add_argument("notebook"); ap.add_argument("analysis"); ap.add_argument("catalog", nargs="?")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--variant", action="append", default=[], help='e.g. "chorus=B"')
    a = ap.parse_args()
    nb = A.load(a.notebook); an = A.load(a.analysis); cat = A.load(a.catalog) if a.catalog else None
    choices = dict(v.split("=", 1) for v in a.variant)
    out = bind(nb, an, cat, choices)
    A.save(out, a.out)
    print(f"bound {len(out['layers'])} layer(s): " + ", ".join(f"{L['id']} {L['name']} [{L['route']}] {L['anchors']['enter']['bar']}:{L['anchors']['enter']['beat']:g}-{L['anchors']['exit']['bar']}:{L['anchors']['exit']['beat']:g}" for L in out["layers"]))
    for q in out["questions"]:
        print("ASK:", q)


if __name__ == "__main__":
    main()
