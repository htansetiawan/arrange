#!/usr/bin/env python3
"""paper_numbers.py - every number of paper Section 5.1 "The composer's own corrections", from the stored answers in
results/*.json (no model is called). Uses rescore.py's rules (record's alternatives, justified questions) and
the first scorer's stored collateral counts.

    python3 paper_numbers.py            # prints the numbers; writes rescored-draws.json next to this file

The sounds the singer gets are recomputed with phonemes_{old,new}.py (g2p_en) for the phoneme items; results are
memoised by content hash in cache-pn/ so a second run is fast.
"""
import hashlib, json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import run_lyrics as L  # noqa: E402
import rescore as RS  # noqa: E402  (installs the rescore rules into run_lyrics)

L.CACHE = HERE / "cache"
_sounds0 = L.sounds


def sounds_memo(rows, pron, ver, key=None):
    if key:
        return _sounds0(rows, pron, ver, key=key)
    h = hashlib.sha256(json.dumps([[{k: v for k, v in r.items() if k != "_o"} for r in rows], pron or {}, ver],
                                  sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    return _sounds0(rows, pron, ver, key="h-" + h)


L.sounds = sounds_memo
CLAUDE = ["claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5"]
OPEN = ["gemma-4-31b-fp8", "qwen3.5-27b-fp8"]


def sign_p(b, w):
    """Two-sided exact sign test (ties dropped)."""
    n = b + w; k = min(b, w)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def main():
    if not (HERE / "items").exists():
        # the fits are not distributed: use the stored per-draw outcomes that this script wrote from them
        draws = json.load(open(HERE / "rescored-draws.json"))
        its = sorted({d["item"] for d in draws})
        return report(draws, its)
    L.CACHE.mkdir(exist_ok=True)
    its = {i["id"]: i for i in L.items()}
    draws = []   # one record per stored answer
    for f in sorted((HERE / "results").glob("*.json")):
        res = json.load(open(f)); m = res["model"]
        for r in res["rows"]:
            if r["id"] not in its:
                continue
            for arm, D in r["draws"].items():
                for d in D:
                    if L.LIMIT.search(d.get("raw", "")[:300]):
                        continue
                    x = RS.rescore_one(its[r["id"]], arm, d)
                    draws.append({"model": m, "arm": arm, "item": r["id"], "cat": its[r["id"]]["cat"], **x,
                                  "n_collateral_stored": d["score"].get("n_collateral", 0), "outcome_stored": d["outcome"]})
    (HERE / "rescored-draws.json").write_text(json.dumps(draws, indent=1))
    return report(draws, its)


def report(draws, its):

    def sel(**kw):
        return [d for d in draws if all((d[k] in v) if isinstance(v, (list, tuple, set)) else d[k] == v for k, v in kw.items())]

    def rate(D, q=False):
        return sum(d["edit"] or (q and d["ask"]) for d in D) / len(D)

    print(f"items scored: {len(its)} (incomplete requests: {len(RS.INCOMPLETE & set(its))})")
    print("\n== accepted (edit only) and typed + justified question, per model")
    for m in CLAUDE + OPEN:
        row = {a: rate(sel(model=m, arm=a)) for a in ("typed", "free", "bare")}
        print(f"{m:<20} typed {row['typed']:.2f} (+q {rate(sel(model=m, arm='typed'), True):.2f})  free {row['free']:.2f}  bare {row['bare']:.2f}"
              f"  n={len(sel(model=m, arm='typed'))}")
    print("\n== paired over items x models (Claude), count of accepted draws per (model, item), sign test two-sided")
    for a, b in (("typed", "bare"), ("free", "bare"), ("typed", "free")):
        bet = wor = tie = 0
        for m in CLAUDE:
            for i in its:
                x = sum(d["edit"] for d in sel(model=m, arm=a, item=i)); y = sum(d["edit"] for d in sel(model=m, arm=b, item=i))
                bet += x > y; wor += x < y; tie += x == y
        print(f"{a} vs {b}: {bet} better, {wor} worse, {tie} tied, p = {sign_p(bet, wor):.4f}")
    print(f"\n== unrelated rows changed per try (first scorer's stored n_collateral, {len(its)} items)")
    for m in CLAUDE + OPEN:
        print(f"{m:<20} " + "  ".join(f"{a} {sum(d['n_collateral_stored'] for d in sel(model=m, arm=a)) / len(sel(model=m, arm=a)):.2f}" for a in ("typed", "free", "bare")))
    print("\n== by category (accepted edits / tries), pooled")
    for grp, ms in (("Claude", CLAUDE), ("open", OPEN)):
        for c in [c for c in ("timing", "fitting", "phoneme", "words") if sel(model=ms, cat=c)]:
            print(f"{grp:<7} {c:<8} " + "  ".join(f"{a} {sum(d['edit'] for d in sel(model=ms, arm=a, cat=c))}/{len(sel(model=ms, arm=a, cat=c))}" for a in ("typed", "free", "bare")))
    print("\n== invalid answers (did not parse / apply), per model and arm")
    for m in CLAUDE + OPEN:
        print(f"{m:<20} " + "  ".join(f"{a} {sum(d['invalid'] for d in sel(model=m, arm=a))}/{len(sel(model=m, arm=a))}" for a in ("typed", "free", "bare")))


if __name__ == "__main__":
    main()
