#!/usr/bin/env python3
"""coverage.py — bar-coverage ballpark for an arrangement notebook (badged ROUGH).

    python3 coverage.py ARRANGEMENT.md piano-analysis.json

Reports, per cell: which layers sound in which bars, which bars have piano
only (often correct — the report says so, it does not call it a gap), and
any component whose @bar/~bars fall outside its cell. Cells without a bar
range take the analysis's section of the same name. No seconds anywhere.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from notebook import parse  # noqa: E402


def main():
    nb = parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
    an = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else {"sections": []}
    sec = {s["label"].lower(): (s["bar_start"], s["bar_end"]) for s in an.get("sections", [])}
    last_bar = max([s["bar_end"] for s in an.get("sections", [])] or [0])
    occupied = {}
    print("ROUGH bar coverage — bars only, nothing here is timing\n")
    for c in nb["cells"]:
        rng = c["bars"] or sec.get(c["name"].lower())
        if not rng:
            print(f"## {c['name']}: no bar range in heading and no matching section in the analysis — ASK");
            continue
        a, b = rng
        print(f"## {c['name']}{' (variant '+c['variant']+')' if c['variant'] else ''}  bars {a}–{b}")
        layers = [k for k in c["components"] if k["type"] not in ("lyrics", "unknown")]
        if not layers:
            print("   piano alone" + ("  (prose says so)" if c["note"] else "  — intended? say so in prose"))
        for k in layers:
            s, e = a, b
            if k.get("enter"):
                s = k["enter"]["bar"]
            if k.get("span"):
                s, e = k["span"]["bar_start"], k["span"]["bar_end"]
            flag = "" if a <= s <= e <= b else "  !! outside this cell's bars"
            print(f"   {k['type']:<10} bars {s}–{e}{flag}")
            if c["variant"] in (None, "A"):
                for bar in range(s, e + 1):
                    occupied.setdefault(bar, set()).add(k["type"])
    if last_bar:
        alone = [b for b in range(1, last_bar + 1) if b not in occupied]
        print(f"\npiano-only bars (variant A path): {len(alone)} of {last_bar}" + (f" — {alone[:12]}{'…' if len(alone) > 12 else ''}" if alone else ""))


if __name__ == "__main__":
    main()
