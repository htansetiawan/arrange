"""S1 turn 4 ('Put the brass back in'): per model and arm, draws where the turn was done right (turn_ok),
and draws where the turn's own intended paths are still off gold after the turn (intended & drift)."""
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
for d in sorted(p for p in root.iterdir() if p.is_dir()):
    for arm in ("typed", "patch", "free", "bare"):
        rows = [json.load(open(f)) for f in sorted(d.glob(f"S1-{arm}-d*.json"))]
        t = [r["turns"][3] for r in rows]
        assert all("brass back" in x["text"] for x in t)
        ok = sum(x["turn_ok"] for x in t)
        miss = sum(bool(set(x["intended"]) & set(x["drift"])) for x in t)
        rej = sum(not x["ok_parse"] for x in t)
        print(f"{d.name:20s} {arm:6s} turn_ok {ok}/{len(t)}  intended-still-off {miss}/{len(t)}  rejected {rej}")
claude = [d for d in root.iterdir() if d.name.startswith("claude")]
print("\nClaude models pooled (3 models x 3 draws):")
for arm in ("typed", "patch", "free", "bare"):
    t = [json.load(open(f))["turns"][3] for d in claude for f in sorted(d.glob(f"S1-{arm}-d*.json"))]
    print(f"  {arm:6s} failed (not turn_ok) {sum(not x['turn_ok'] for x in t)}/{len(t)}; intended paths off {sum(bool(set(x['intended']) & set(x['drift'])) for x in t)}/{len(t)}")
