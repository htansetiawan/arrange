#!/usr/bin/env python3
"""merge_take.py — put a saved take into the fit, replacing only the stretch it covers (/arrange-lyrics; plain python).

    python merge_take.py arrange-project.json --take take.json --grid grid.json [--words "line one" --words "line two"]

The take (from the Play the Line page's store) and the composer's beat grid
(taps and nudge) go through take.py: taps become the tempo map, the composer's lead is
removed, notes snap to quarter beats, doubled notes merge, fumbles are
reported. Then every row of the current fit that sits inside the take's span
is replaced by the take's rows; everything before and after is kept. Words
come from --words (one per phrase of the take) or the take's own words box;
without words the new notes are placed grey, for the composer to name.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--take", required=True); ap.add_argument("--grid", required=True); ap.add_argument("--words", action="append", default=[])
    a = ap.parse_args()
    cfg = arrange_config.load(); proj, base = arrange_config.project(a.project)
    take = json.load(open(a.take)); take = take.get("data", take)
    words = a.words or [w.strip() for w in (take.get("words") or "").split("/") if w.strip()]
    with tempfile.TemporaryDirectory(prefix="arrange-take-") as tmp:
        lines = Path(tmp) / "lines.txt"; lines.write_text("\n".join(words) + ("\n" if words else ""))
        tapped = Path(proj.get("analysis_tapped", base / "piano-analysis.tapped.json"))
        r = subprocess.run([cfg["python"]["plain"], str(HERE / "take.py"), "--take", a.take, "--grid", a.grid, "--analysis", proj["analysis_measured"],
                            "--lines", str(lines), "--out-analysis", str(tapped), "-o", tmp], capture_output=True, text=True)
        print(r.stdout, end=""); 
        if r.returncode:
            sys.exit(r.stderr[-800:])
        new = json.load(open(Path(tmp) / "score-with-unsung.json"))["rows"]
    if not new:
        sys.exit("the take has no notes")
    fit = json.load(open(proj["fit"])); old = fit["rows"]
    t0, t1 = new[0]["t"] - 0.1, new[-1]["end"] + 0.1
    kept = [r for r in old if r["end"] <= t0 or r["t"] >= t1]
    rows = sorted(kept + new, key=lambda r: r["t"])
    for k, r in enumerate(rows):
        r["index"] = k
    fit["rows"] = rows; fit.setdefault("report", []).append(f"take {Path(a.take).stem}: replaced {len(old) - len(kept)} notes between {t0:.1f} and {t1:.1f} s with {len(new)}")
    json.dump(fit, open(proj["fit"], "w"), indent=1, ensure_ascii=False)
    raw = json.loads(Path(a.project).read_text()); raw["analysis"] = str(tapped.relative_to(base)) if str(tapped).startswith(str(base)) else str(tapped); raw["analysis_tapped"] = raw["analysis"]
    Path(a.project).write_text(json.dumps(raw, indent=1))
    print(f"MERGED: {len(old) - len(kept)} notes between {t0:.1f} and {t1:.1f} s replaced by {len(new)}; the rest of the fit kept ({len(kept)} notes)")


if __name__ == "__main__":
    main()
