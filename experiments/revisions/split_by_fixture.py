"""split_by_fixture.py — write summary-real.json and summary-synthetic.json next to a run_e2 summary.json,
so summarize.py can print the per-plan aggregates ("On the real plan alone ...").
    python3 split_by_fixture.py results/summary.json"""
import json, sys
from pathlib import Path
src = Path(sys.argv[1]); S = json.loads(src.read_text())
for fx in ("real", "synthetic"):
    out = dict(S, instructions=[i for i in S["instructions"] if i["fixture"] == fx])
    (src.parent / f"summary-{fx}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote", src.parent / f"summary-{fx}.json", len(out["instructions"]), "requests")
