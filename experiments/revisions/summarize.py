#!/usr/bin/env python3
"""summarize.py — the E2 results as a table the paper can print.

    python3 summarize.py results/summary.json -o results/SUMMARY.md

Per instruction and arm: outcomes of the draws, mean recall and precision of
intended changes, collateral paths per draw, stale-set matches, unsupported
handling, protected-field violations, cost. Then the two arms' aggregates.
Draws are nested within instructions; nothing here is a human result.
"""
import argparse, json, statistics as st
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("summary"); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    S = json.load(open(a.summary))
    lines = [f"# E2 revision suite — {S['model']}, {S['draws']} draws per instruction and arm", "",
             "Typed = the model answers with operations from the frozen vocabulary, applied deterministically. Free = the same model re-emits the whole edited plan JSON. Patch = the same model names paths and values to change (no re-emission). Same schema notes, same validator, same clock; derived seconds and ownership bookkeeping are excluded from the change counts. Recall and precision are over the JSON paths changed against the gold diff (expected operations applied to the frozen fixture). Collateral = paths changed outside the gold set. Stale = the set of layers marked for re-render matches the gold. Unsupported = for ambiguous or impossible requests, a visible question with no plan change. Protected = changes to fields the creator owns that the gold does not touch.", "",
             "| id | fixture | instruction | arm | outcomes | recall | precision | collateral/draw | stale ok | unsupported ok | protected viol. | cost $ |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    agg = {"typed": [], "free": [], "patch": []}
    for inst in S["instructions"]:
        for arm in ("typed", "free", "patch"):
            ds = inst["draws"].get(arm) or []
            if not ds:
                continue
            rec = st.mean(d["score"]["recall"] for d in ds); prec = st.mean(d["score"]["precision"] for d in ds)
            col = st.mean(len(d["score"]["collateral"]) for d in ds); stale = sum(d["score"]["stale_match"] for d in ds)
            uns = [d["score"]["unsupported_ok"] for d in ds if d["score"]["unsupported_ok"] is not None]
            prot = sum(len(d["score"]["protected_violations"]) for d in ds)
            cost = sum((d.get("usage") or {}).get("total_cost_usd") or 0 for d in ds)
            outs = ", ".join(d["outcome"] for d in ds)
            lines.append(f"| {inst['id']} | {inst['fixture']} | {inst['text']} | {arm} | {outs} | {rec:.2f} | {prec:.2f} | {col:.1f} | {stale}/{len(ds)} | {('%d/%d' % (sum(uns), len(uns))) if uns else '—'} | {prot} | {cost:.2f} |")
            agg[arm].append({"rec": rec, "prec": prec, "col": col, "stale": stale / len(ds), "prot": prot, "uns": uns, "outs": [d["outcome"] for d in ds], "cost": cost})
    lines += ["", "## Aggregates", "", "| arm | instructions | mean recall | mean precision | collateral/draw | stale ok | unsupported ok | protected viol. | outcomes | cost $ |", "|---|---|---|---|---|---|---|---|---|---|"]
    for arm, rows in agg.items():
        if not rows:
            continue
        uns = [u for r in rows for u in r["uns"]]
        outs = {}
        for r in rows:
            for o in r["outs"]:
                outs[o] = outs.get(o, 0) + 1
        lines.append(f"| {arm} | {len(rows)} | {st.mean(r['rec'] for r in rows):.2f} | {st.mean(r['prec'] for r in rows):.2f} | {st.mean(r['col'] for r in rows):.1f} | {st.mean(r['stale'] for r in rows):.2f} | {('%d/%d' % (sum(uns), len(uns))) if uns else '—'} | {sum(r['prot'] for r in rows)} | {', '.join(f'{k} {v}' for k, v in sorted(outs.items()))} | {sum(r['cost'] for r in rows):.2f} |")
    lines += ["", "Caveats: draws are repeated samples of one model on one instruction, not independent tasks or users; the comparison is between two encodings of the same assistant, not between a system and a person; the fixtures and gold were frozen before any call (hashes in synthetic/FROZEN.sha256 and real/FROZEN.sha256)."]
    Path(a.out).write_text("\n".join(lines) + "\n")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
