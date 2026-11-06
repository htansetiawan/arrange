#!/usr/bin/env python3
"""edit_fit.py — apply a list of edits to the sung line, all or nothing, and print the fit as it is now.

    python3 edit_fit.py '[{"op":"set","row":19,"pitch":"D5"}, ...]' [--song song]
"""
import argparse, json
import fitlib

ap = argparse.ArgumentParser(); ap.add_argument("edits"); ap.add_argument("--song", default="song"); a = ap.parse_args()
fit, pron, clock = fitlib.load(a.song)
ops = json.loads(a.edits); ops = [ops] if isinstance(ops, dict) else ops
try:
    rows, pron = fitlib.apply(fit["rows"], pron, ops, clock)
except Exception as e:  # noqa: BLE001
    raise SystemExit(f"REFUSED, nothing changed: {e}")
fit["rows"] = rows; fitlib.save(a.song, fit, pron)
print(f"APPLIED {len(ops)} edit(s). The fit now (row numbers may have changed):\n" + fitlib.table(rows))
print("\nPRONOUNCE FILE: " + json.dumps(pron, ensure_ascii=False))
