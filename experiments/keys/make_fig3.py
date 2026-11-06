#!/usr/bin/env python3
"""make_fig3.py: Figure 3 of the paper. Each rule's key minus the key the composer chose on the side-by-side ladder,
one row per voice, with that key beside the voice's name. Lanes within a row, top to bottom: Top note, Top, Median, Clip.

    python3 make_fig3.py              # figures/fig3.png, figures/fig3.svg, figures/fig3.csv
    python3 make_fig3.py --print      # the data only, no matplotlib needed

Reads the side-by-side answers and key (side-by-side/) and the rule keys (data/profiles.json). No model, no audio.
"""
import argparse, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORDER = ["groban", "adams", "clarkson", "ariana", "jackson", "bolton", "wonder", "buble"]
LABEL = {"groban": "Groban", "adams": "Adams", "clarkson": "Clarkson", "ariana": "Ariana", "jackson": "Jackson",
         "bolton": "Bolton", "wonder": "Wonder", "buble": "Bublé"}
RULES = [("topnote", "Top note"), ("top", "Top"), ("median", "Median"), ("clip", "Clip")]


def rows():
    key = json.load(open(HERE / "side-by-side/key.json")); ref = {}
    for f in sorted((HERE / "side-by-side/answers").glob("*.json")):
        d = json.load(open(f)); ref[key[d["sweet"]]["voice"]] = key[d["sweet"]]["shift"]
    rules = json.load(open(HERE / "data/profiles.json"))["rules"]
    out = []
    for v in ORDER:
        r = rules[f"attya/{v}"]
        out.append({"voice": v, "reference": ref[v], **{k: r[k] for k, _ in RULES}, **{f"err_{k}": r[k] - ref[v] for k, _ in RULES}})
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--print", action="store_true", help="print the data, write nothing")
    ap.add_argument("--out", default=str(HERE / "figures"))
    a = ap.parse_args(); data = rows()
    print("voice      reference  " + "  ".join(f"{lab:>8s}" for _, lab in RULES) + "   (rule's key minus the reference)")
    for r in data:
        print(f"{LABEL[r['voice']]:10s} {r['reference']:+9d}  " + "  ".join(f"{r[f'err_{k}']:+8d}" for k, _ in RULES))
    if a.print:
        return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    cols = list(data[0])
    (out / "fig3.csv").write_text(",".join(cols) + "\n" + "".join(",".join(str(r[c]) for c in cols) + "\n" for r in data))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    matplotlib.rcParams["svg.hashsalt"] = "fig3"          # stable ids in the SVG
    col = {"topnote": "#2a78d6", "top": "#eb6834", "median": "#1baf7a", "clip": "#eda100"}
    lane = {"topnote": -0.27, "top": -0.09, "median": 0.09, "clip": 0.27}
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=200); fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
    for i, r in enumerate(data):
        for k, lab in RULES:
            y, e = i + lane[k], r[f"err_{k}"]
            ax.plot([0, e], [y, y], color=col[k], lw=2, solid_capstyle="round", zorder=2)
            ax.plot([e], [y], "o", ms=6, color=col[k], mec="#fcfcfb", mew=1.5, zorder=3, label=lab if i == 0 else None)
    ax.axvline(0, color="#52514e", lw=1, zorder=1)
    ax.set_yticks(range(len(data))); ax.set_yticklabels([f"{LABEL[r['voice']]}  ({r['reference']:+d})" for r in data], color="#0b0b0b")
    ax.invert_yaxis(); ax.set_xlim(-6, 10); ax.set_xticks(range(-6, 11, 2))
    ax.grid(axis="x", color="#e6e5e0", lw=0.6, zorder=0)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_xlabel("rule's key minus the composer's pick (semitones; + = too high)", color="#52514e")
    ax.legend(loc="upper right", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig3.png", metadata={"Software": None})
    fig.savefig(out / "fig3.svg", metadata={"Date": None, "Creator": None})
    print("wrote", ", ".join(str((out / f).relative_to(HERE)) for f in ("fig3.png", "fig3.svg", "fig3.csv")))


if __name__ == "__main__":
    main()
