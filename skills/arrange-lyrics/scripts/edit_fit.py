#!/usr/bin/env python3
"""edit_fit.py — apply a list of edits to the project's fit, all or nothing, and print the fit as it is now (plain python).

    python edit_fit.py arrange-project.json '[{"op":"set","row":19,"pitch":"D5"}, ...]'

Row numbers are the idx column of show_fit.py as it is before this call; every edit in one call refers to those
numbers. The edits (see SKILL.md, "Change the fit"):
  {"op":"set","row":i, ...any of "text","kind","word","pitch" (e.g. "A4"),"t","end" (seconds)}
  {"op":"move","row":i,"bar":b,"beat":x}      start the note at the canvas bar/beat; it keeps its length unless "end" is given
  {"op":"shift","rows":[i,...],"by":s}        move these notes by s seconds (negative = earlier)
  {"op":"insert","after":i,"pitch":"G4","kind":"note","text":"...","word":"...","t":s,"end":s}
  {"op":"delete","row":i}
  {"op":"pronounce","word":"Footsteps","sounds":["F UH1","T S EH1 P S"]}
A refused call changes nothing. The fit's report gets one line per applied call.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("edits"); a = ap.parse_args()
P = fitlib.load(a.project)
try:
    ops = json.loads(a.edits); ops = [ops] if isinstance(ops, dict) else ops
    rows, pron = fitlib.apply(P["fit"]["rows"], P["pron"], ops, P["canvas"])
except Exception as e:  # noqa: BLE001
    raise SystemExit(f"REFUSED, nothing changed: {e}")
P["fit"].setdefault("report", []).append("edited by row: " + json.dumps(ops, ensure_ascii=False))
fitlib.save(P, rows, pron)
print(f"APPLIED {len(ops)} edit(s). The fit now (row numbers may have changed):\n" + fitlib.table(rows, P["canvas"]))
print("\nPRONOUNCE FILE: " + json.dumps(pron, ensure_ascii=False))
