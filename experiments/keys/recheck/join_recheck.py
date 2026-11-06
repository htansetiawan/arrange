#!/usr/bin/env python3
"""join_recheck.py: join the 14 recheck answers with the clip key, in the order answered.

    python3 join_recheck.py           # recheck-joined.json (read by ../side-by-side/analyze_side_by_side.py)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
key = json.load(open(HERE / "key.json")); rows = []
for f in sorted((HERE / "answers").glob("*.json")):
    a = json.load(open(f)); k = key[a["clip"]]
    rows.append({"voice": k["voice"], "shift": k["shift"], "strain": a["strain"], "register": a["register"], "broken": a.get("broken", False), "at": a.get("at")})
rows.sort(key=lambda r: r["at"])
json.dump(rows, open(HERE / "recheck-joined.json", "w"), indent=1); print(len(rows), "rows")
