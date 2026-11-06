#!/usr/bin/env python3
"""revise.py — apply typed revisions to arrangement.json, deterministically.

    python3 revise.py apply arrangement.json piano-analysis.json --ops ops.json  [--actor creator] [--reason "..."]
                      [--catalog asset-catalog.json] [-o arrangement.json] [--analysis-out piano-analysis.json] [--report report.json]
    python3 revise.py ops                                   # print the operation vocabulary

`ops.json` is a list of operations. Turning the creator's words into
operations is the language model's job (or a person's); this script only
applies them, checks them against the clock and the plan, refuses what it
cannot do with a reason, records open questions, marks stale layers, and
prints exactly what changed. Nothing is dropped silently: every operation
ends up in `applied`, `refused` or `unresolved`.

Operation vocabulary (fixed; see `revise.py ops`):
  set_entry   {layer, bar, beat?}          shift_entry {layer, by_bars?, by_beats?}
  set_exit    {layer, bar, beat?}          shift_exit  {layer, by_bars?, by_beats?}   (exits are exclusive)
  set_context {layer, audio_context: [ids]}            choose_candidate {layer, candidate: id | 1-based number}
  set_gain    {layer, db}                              replace_with_take {layer, asset}
  set_stub    {layer, reason}                          unstub {layer}
  set_class   {layer, class, text?, name?}             add_layer {name?, class, text?, cell?, enter{bar,beat}, exit{bar,beat}, route?}
  lock        {layer, fields?: [exists|anchors|route|conditions|prompt|chosen|gain]}
  set_clock   {bar, t}      (moves that bar's downbeat; neighbouring beats re-spaced; a creator correction)
  ask         {question}    (anything the words do not map to; recorded, nothing changed)
A `layer` may be an id (L2), a name (strings) or a class, when unambiguous.
"""
import argparse, json, shutil, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrangement as A  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["apply", "ops"])
    ap.add_argument("arrangement", nargs="?"); ap.add_argument("analysis", nargs="?")
    ap.add_argument("--ops"); ap.add_argument("--op", action="append", default=[], help="one operation as JSON; repeatable")
    ap.add_argument("--actor", default="creator"); ap.add_argument("--reason", default="")
    ap.add_argument("--catalog"); ap.add_argument("-o", "--out"); ap.add_argument("--analysis-out"); ap.add_argument("--report")
    ap.add_argument("--keep", action="store_true", help="keep a copy of the previous revision next to the plan")
    a = ap.parse_args()
    if a.cmd == "ops":
        print(__doc__.split("Operation vocabulary")[1]); return
    if not (a.arrangement and a.analysis):
        ap.error("apply needs arrangement.json and piano-analysis.json")
    ops = A.load(a.ops) if a.ops else []
    ops += [json.loads(o) for o in a.op]
    if not ops:
        ap.error("no operations given (--ops file or --op json)")
    plan, an = A.load(a.arrangement), A.load(a.analysis)
    cat = A.load(a.catalog) if a.catalog else None
    new_plan, new_an, rep = A.apply_ops(plan, an, ops, actor=a.actor, reason=a.reason, catalog=cat)
    problems = A.validate(new_plan, new_an)
    rep["validation"] = problems
    for x in rep["applied"]:
        print("APPLIED:", x["effect"])
    for x in rep["refused"]:
        print("REFUSED:", json.dumps(x["op"]), "->", x["why"])
    for q in rep["unresolved"]:
        print("OPEN QUESTION:", q)
    if rep["stale"]:
        print("STALE (needs re-render):", ", ".join(f"{s} ({A.layer_by_id(new_plan, s)['stale_reason']})" for s in rep["stale"]))
    print(f"CHANGED PATHS ({len(rep['diff'])}):", ", ".join(c["path"] for c in rep["diff"]) or "none")
    for p in problems:
        print("INVALID AFTER REVISION:", p)
    if problems:
        print("plan NOT written: the revision would leave an invalid plan")
        if a.report:
            A.save(rep, a.report)
        sys.exit(1)
    out = a.out or a.arrangement
    if a.keep and Path(out).exists():
        shutil.copy(out, str(out) + f".rev{plan.get('revision', 0)}")
    A.save(new_plan, out)
    if a.analysis_out or new_an != an:
        A.save(new_an, a.analysis_out or a.analysis)
    if a.report:
        A.save(rep, a.report)
    print(f"revision {new_plan.get('revision')} written to {out}")
    sys.exit(0 if not rep["refused"] else 2)


if __name__ == "__main__":
    main()
