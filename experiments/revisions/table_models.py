"""table_models.py — T1: does ARRANGE matter, across models? One row per model and arm over the 16 frozen requests x draws.

    python3 table_models.py      # reads results/ (Sonnet, 31 Oct) and results-models/<model>/; writes results-models/TABLE.md

correct     the draw changed exactly the gold paths (recall 1, precision 1) and, for impossible/ambiguous requests,
            asked instead of editing
collateral  paths changed outside the gold set, per draw
overwrote   changes to fields the composer owns that the request did not touch, per 48 draws
invalid     the answer could not be parsed or failed the plan validator
typed = ARRANGE's edit vocabulary, applied and checked by the skill; patch = named paths, written as given (no protection
check); free = the model rewrites the whole plan, with ARRANGE's schema notes; bare = the same rewrite with no ARRANGE notes. Paired test: per request, mean correct with ARRANGE (typed) vs without (free), Wilcoxon.
"""
import json, random
from pathlib import Path

from scipy.stats import wilcoxon

E2 = Path(__file__).parent
SOURCES = {"claude-sonnet-5-5 (31 Oct)": E2 / "results"}
for d in sorted((E2 / "results-models").glob("*")):
    if d.is_dir() and not d.name.startswith(("pilot", "dry")):
        SOURCES[d.name] = d
ARMS = [("typed", "with ARRANGE (typed ops)"), ("patch", "with ARRANGE (patch)"), ("free", "ARRANGE notes, free rewrite"), ("bare", "no ARRANGE at all (bare rewrite)")]


def correct(r):
    s = r["score"]
    if s.get("unsupported_ok") is not None:
        return bool(s["unsupported_ok"])
    return r["outcome"] != "invalid" and s["recall"] == 1 and s["precision"] == 1


def boot(xs, n=2000):
    rng = random.Random(1); m = len(xs)
    means = sorted(sum(rng.choice(xs) for _ in range(m)) / m for _ in range(n))
    return means[int(.025 * n)], means[int(.975 * n)]


lines = ["# T1 — ARRANGE across models (E2, 16 frozen requests x 3 draws)", "",
         "| model | arm | correct (95% CI) | collateral / draw | overwrote composer | invalid | cost $ |", "|---|---|---|---|---|---|---|"]
tests = []
for model, d in SOURCES.items():
    files = sorted(d.glob("[a-h][12].json"))
    if len(files) < 16:
        lines.append(f"| {model} | (incomplete: {len(files)}/16 requests) | | | | | |"); continue
    recs = [json.loads(f.read_text()) for f in files]
    per_req = {}
    for arm, label in ARMS:
        draws = [r for rec in recs for r in rec["draws"].get(arm, [])]
        if not draws:
            continue
        c = [1.0 if correct(r) else 0.0 for r in draws]
        lo, hi = boot(c)
        col = sum(len(r["score"]["collateral"]) for r in draws) / len(draws)
        viol = sum(len(r["score"]["protected_violations"]) for r in draws)
        inv = sum(r["outcome"] == "invalid" for r in draws)
        cost = sum((r.get("usage") or {}).get("total_cost_usd") or 0 for r in draws)
        lines.append(f"| {model} | {label} | {sum(c) / len(c):.2f} ({lo:.2f}-{hi:.2f}) | {col:.1f} | {viol} | {inv}/{len(draws)} | {cost:.2f} |")
        per_req[arm] = [sum(correct(r) for r in rec["draws"][arm]) / max(1, len(rec["draws"].get(arm, []))) for rec in recs]
    for other in ("free", "bare"):
        if "typed" not in per_req or other not in per_req:
            continue
        diff = [a - b for a, b in zip(per_req["typed"], per_req[other])]
        nz = [x for x in diff if x]
        p = wilcoxon(nz).pvalue if len(nz) >= 2 else float("nan")
        tests.append(f"- {model}: typed − {other} = {sum(diff) / len(diff):+.2f} per request (better on {sum(x > 0 for x in diff)}, "
                     f"worse on {sum(x < 0 for x in diff)}, same on {sum(x == 0 for x in diff)} of 16), Wilcoxon p = {p:.3f}")
lines += ["", "Paired by request (typed vs free rewrite with ARRANGE notes, and vs bare rewrite with no ARRANGE):", *tests]
(E2 / "results-models/TABLE.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
