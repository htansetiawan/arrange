"""canvas_pos.py — bar and beat of every fit row as the score canvas numbers them (same code path as canvas.py:
notate.quantise on the measured clock, then --beat-offset, bar = ordinal*per // bpb + 1). Beats are the composer's beats."""
import json, sys
from pathlib import Path
X = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(X / "skills/arrange-lyrics/scripts"))
import canvas, notate  # noqa: E402

def positions(project_dir):
    D = Path(project_dir); proj = json.load(open(D / "arrange-project.json"))
    an = json.load(open(D / (proj.get("analysis") or proj["analysis_measured"])))
    fit = json.load(open(D / proj["fit"])); rows = list(fit["rows"])
    clk = canvas.Clock(an); per, bpb, ts = canvas.feel(an)
    q = notate.quantise([dict(r) for r in rows], clk, proj.get("score_grid") or 4)
    out = []
    for r in q:
        o = (r["ordinal"] + proj.get("beat_offset", 0) / per) * per
        out.append({"bar": int(o // bpb) + 1, "beat": round(o % bpb + 1, 3)})
    return proj, an, fit, out, (per, bpb, ts)

if __name__ == "__main__":
    proj, an, fit, pos, f = positions(sys.argv[1])
    print(proj["title"], "per/bpb/ts", f, "rows", len(pos))
    diff = sum(p["bar"] != r.get("bar") for p, r in zip(pos, fit["rows"]))
    print("rows whose canvas bar differs from the map bar:", diff)
    for p, r in list(zip(pos, fit["rows"]))[:8]:
        print(f"  map {r.get('bar')}.{r.get('beat')}  canvas {p['bar']}.{p['beat']}  {r.get('text')!r} {r.get('kind')}")


def canvas_clock(project_dir):
    """(bar, beat) as the canvas numbers them -> seconds in the recording."""
    sys.path.insert(0, str(X / "skills/arrange-plan/scripts"))
    from clock import Clock
    D = Path(project_dir); proj = json.load(open(D / "arrange-project.json"))
    an = json.load(open(D / (proj.get("analysis") or proj["analysis_measured"])))
    clk = Clock(an); per, bpb, ts = canvas.feel(an); off = proj.get("beat_offset", 0)

    def t_of(bar, beat):
        c = (bar - 1) * bpb + (beat - 1)          # canvas ordinal in his beats
        mb, mt = clk._position(c / per - off / per)
        return clk.t(mb, mt, extrapolate=True)[0]
    return t_of
