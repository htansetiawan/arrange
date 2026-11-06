#!/usr/bin/env python3
"""build.py — assemble arrangement.json from bindings, derive seconds, preserve creator decisions.

    python3 build.py build notebook.json bindings.json piano-analysis.json -o arrangement.json [--preserve old-arrangement.json]

With --preserve, every field the creator owns in the old plan survives: a
layer is matched by cell + class + name; its creator-owned anchors, route,
conditions, chosen candidate and candidates are copied over the fresh
binding. A real conflict (the notebook now says something different from a
creator decision) is kept on the creator's side and raised as a question.
"""
import argparse, copy, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrangement as A  # noqa: E402


def preserve(new_layers, old_plan, questions):
    old = {(L["from"].get("cell"), L.get("class"), L["name"]): L for L in old_plan["layers"]}
    for L in new_layers:
        key = (L["from"].get("cell"), L.get("class"), L["name"])
        o = old.get(key)
        if not o:
            continue
        for f, src in (("anchors", "anchors"), ("route", "route"), ("conditions", "conditions"), ("chosen", "chosen"), ("gain", "gain_db")):
            if o.get("owner", {}).get(f) == "creator":
                if L.get(src) != o.get(src):
                    questions.append(f"{L['id']} ({L['name']}): you decided {f} = {o.get(src)} earlier; the notebook now implies {L.get(src)}. Your decision is kept.")
                L[src] = copy.deepcopy(o.get(src)); L["owner"][f] = "creator"
                if f == "route":
                    L["kind"] = o["kind"]; L["job"] = copy.deepcopy(o.get("job")); L["asset"] = o.get("asset"); L["stub_reason"] = o.get("stub_reason")
        for f in ("candidates", "stale", "stale_reason", "status", "chosen"):
            if f in o:
                L[f] = copy.deepcopy(o[f])
        if L.get("lyrics") != o.get("lyrics") and o.get("candidates"):
            L["stale"], L["stale_reason"], L["status"] = True, "the lyrics changed in the notebook after this layer was rendered", "stale"
            questions.append(f"{o['id']} ({L['name']}): the words changed; its {len(o['candidates'])} rendered candidate(s) are stale and it will be re-rendered. Layers that heard it are stale too.")
        L["id"] = o["id"]
    return new_layers


def build(nb, bindings, analysis, old_plan=None):
    questions = list(bindings.get("questions", []))
    layers = copy.deepcopy(bindings["layers"])
    if old_plan:
        layers = preserve(layers, old_plan, questions)
    order = [L["id"] for L in layers]
    sections = copy.deepcopy(analysis.get("sections", []))
    for c in bindings.get("cells", []):
        for s in sections:
            if s["label"].lower() == c["name"].lower() and c.get("bars"):
                s["bar_start"], s["bar_end"] = c["bars"]
    plan = {"schema": A.SCHEMA, "piece": nb.get("piece"), "revision": (old_plan or {}).get("revision", 0),
            "inputs": {"analysis": "piano-analysis.json", "notebook": "ARRANGEMENT.md"},
            "clock": {}, "sections": sections,
            "spine": {"id": "piano", "kind": "take", "path": analysis.get("source", {}).get("path"), "sha256": analysis.get("source", {}).get("sha256"), "class": "keyboard"},
            "layers": layers, "order": order,
            "open": {"questions": questions,
                     "unresolved_specs": list(analysis.get("unresolved", [])) + list(analysis.get("tempo_map", {}).get("unresolved", []))},
            "export": {"target": "logic", "sr": analysis.get("source", {}).get("sr", 48000), "bit_depth": 24, "preroll_bars": 1},
            "history": (old_plan or {}).get("history", [])}
    for L in plan["layers"]:
        if L["route"] == "audio":
            A.default_conditions(plan, L) if L["owner"].get("conditions") != "creator" else None
    if old_plan:
        changed = [L["id"] for L in plan["layers"] if L.get("stale") and not next((o for o in old_plan["layers"] if o["id"] == L["id"]), {}).get("stale")]
        if changed:
            A.mark_stale(plan, changed, "a layer it depends on changed in the notebook")
        plan["history"] = list(old_plan.get("history", [])) + [{"revision": int(old_plan.get("revision", 0)) + 1, "actor": "creator", "reason": "notebook edited and rebuilt",
                                                                 "ops": [{"op": "rebuild", "notebook": "ARRANGEMENT.md"}], "applied": [f"{q}" for q in questions if "stale" in q],
                                                                 "refused": [], "unresolved": [], "stale": [L["id"] for L in plan["layers"] if L.get("stale")], "paths": []}]
        plan["revision"] = int(old_plan.get("revision", 0)) + 1
    problems = A.derive_times(plan, analysis)
    return plan, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("notebook"); ap.add_argument("bindings"); ap.add_argument("analysis")
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--preserve")
    a = ap.parse_args()
    plan, problems = build(A.load(a.notebook), A.load(a.bindings), A.load(a.analysis), A.load(a.preserve) if a.preserve else None)
    v = A.validate(plan, A.load(a.analysis))
    A.save(plan, a.out)
    for L in plan["layers"]:
        ctx = L["conditions"].get("audio_context") or []
        print(f"{L['id']:<4}{L['name']:<10}{L['route']:<6}{L['anchors']['enter']['bar']}:{L['anchors']['enter']['beat']:g}-{L['anchors']['exit']['bar']}:{L['anchors']['exit']['beat']:g}  {L['t0']:>8.3f}s-{L['t1']:<8.3f}s  hears {ctx}  owner {sorted(k for k,v in L['owner'].items() if v=='creator')}")
    for q in plan["open"]["questions"]:
        print("ASK:", q)
    for q in plan["open"]["unresolved_specs"]:
        print("UNRESOLVED:", q)
    for p in problems + v:
        print("PROBLEM:", p)
    print(f"wrote {a.out}: {len(plan['layers'])} layers, {'valid' if not (problems or v) else 'INVALID'}")
    sys.exit(1 if (problems or v) else 0)


if __name__ == "__main__":
    main()
