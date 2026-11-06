#!/usr/bin/env python3
"""run_sessions.py — E2s: chained revision sessions. Each turn's input plan is the previous turn's output, as in real use.

    python3 run_sessions.py --model claude-haiku-5-5 --draws 3 [--arms typed patch free bare] [--base-url URL]
    # writes sessions-results/<model>/<session>-<arm>-d<k>.json

Arms and prompts are exactly those of run_e2.py (typed / patch / free / bare). A turn whose answer cannot be parsed or fails
the validator is rejected and the plan stays as it was (the musician would have to ask again); it is counted as a failed
turn. Gold: sessions.json ops applied in order to the frozen fixture.

Scored after every turn, against the gold plan of that turn (editorial JSON paths; derived t0/t1, history, stale flags
excluded): drift = paths where the session's plan differs from gold; new_errors = drift paths that were not there before
this turn; turn_ok = the turn's own intended paths match gold and no new drift; composer_lost = drift paths inside fields
the composer owned in the starting plan; tempo = largest downbeat difference to the gold tempo map (s); stale_missed =
layers the gold marks stale (would need re-rendering) that the arm did not flag, accumulated over the session.
"""
import argparse, concurrent.futures as cf, copy, json, sys, time
from pathlib import Path

E2 = Path(__file__).resolve().parent
sys.path.insert(0, str(E2))
import run_e2 as R  # noqa: E402  (prompts, model call, parsing, scoring helpers)
A, Clock = R.A, R.Clock


def gold_ops(turn, an):
    ops = copy.deepcopy(turn["gold"])
    for op in ops:
        if op["op"] == "set_clock" and isinstance(op.get("t"), str):
            op["t"] = round(Clock(an).t(op["bar"], 1)[0] - 0.5, 3)
    return ops


def sections(plan):
    return json.dumps([{k: s[k] for k in ("label", "bar_start", "bar_end")} for s in plan["sections"]])


def user_msg(plan, text, doc):
    return f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}\n\nSECTIONS: {sections(plan)}\n\nTHE MUSICIAN SAYS: {text}\n\n{doc}"


def turn_typed(plan, an, cat, text, model):
    raw, usage, el = R.call_model(R.SCHEMA_NOTES, user_msg(plan, text, R.OPS_DOC), model)
    try:
        ops = R.extract_json(raw); ops = [ops] if isinstance(ops, dict) else ops
        np_, na, rep = A.apply_ops(plan, an, ops, actor="creator", reason=text, catalog=cat)
        if A.validate(np_, na):
            raise ValueError(f"validator: {A.validate(np_, na)[:3]}")
    except Exception as e:
        return plan, an, {"raw": raw[:3000], "usage": usage, "elapsed": el, "ok": False, "error": str(e)[:300], "stale": []}
    return np_, na, {"raw": raw[:3000], "usage": usage, "elapsed": el, "ok": True, "ops": ops, "refused": rep["refused"], "stale": rep["stale"]}


def turn_rewrite(plan, an, cat, text, model, kind):
    system, doc = {"free": (R.SCHEMA_NOTES, R.FREE_DOC), "bare": (R.BARE_SYSTEM, R.BARE_DOC), "patch": (R.SCHEMA_NOTES, R.PATCH_DOC)}[kind]
    raw, usage, el = R.call_model(system, user_msg(plan, text, doc), model)
    try:
        obj = R.extract_json(raw)
        if kind == "patch":
            new_plan = copy.deepcopy(plan)
            for ed in obj.get("edits") or []:
                R.set_path(new_plan, ed["path"], ed["value"])
        else:
            new_plan = obj["plan"]
        na = copy.deepcopy(an)
        for c in obj.get("tempo_map_corrections") or []:
            na = A.apply_ops(plan, na, [{"op": "set_clock", "bar": c["bar"], "t": c["t"]}], actor="creator", reason=kind)[1]
        A.derive_times(new_plan, na)
        probs = A.validate(new_plan, na)
        if probs:
            raise ValueError(f"validator: {probs[:3]}")
    except Exception as e:
        return plan, an, {"raw": raw[:3000], "usage": usage, "elapsed": el, "ok": False, "error": str(e)[:300], "stale": []}
    return new_plan, na, {"raw": raw[:3000], "usage": usage, "elapsed": el, "ok": True, "stale": obj.get("stale") or [], "questions": obj.get("questions") or []}


def downbeats(an, bars):
    c = Clock(an)
    return {b: c.t(b, 1)[0] for b in bars}


def run_one(sess, fixture, arm, model, k, out_dir):
    plan0, an0, cat = fixture
    protected = R.protected(plan0)
    bars = list(range(1, 42))
    gp, ga = copy.deepcopy(plan0), copy.deepcopy(an0)
    mp, ma = copy.deepcopy(plan0), copy.deepcopy(an0)
    rows, drift_before, stale_missed, cost = [], set(), set(), 0.0
    for i, turn in enumerate(sess["turns"]):
        ops = gold_ops(turn, ga)
        gp2, ga2, grep = A.apply_ops(gp, ga, ops, actor="creator", reason="gold", catalog=cat)
        intended = R.editorial([c["path"] for c in A.diff(gp, gp2)])
        if arm == "typed":
            mp2, ma2, info = turn_typed(mp, ma, cat, turn["text"], model)
        else:
            mp2, ma2, info = turn_rewrite(mp, ma, cat, turn["text"], model, arm)
        drift = R.editorial([c["path"] for c in A.diff(mp2, gp2)])
        db_g, db_m = downbeats(ga2, bars), downbeats(ma2, bars)
        tempo = max(abs(db_g[b] - db_m[b]) for b in bars)
        if tempo > 0.05:
            drift.add("piano-analysis.json#tempo_map")
        if any(op["op"] == "set_clock" for op in ops):
            intended.add("piano-analysis.json#tempo_map")
        new = drift - drift_before
        stale_missed |= set(f"t{i+1}:{s}" for s in grep["stale"]) - set(f"t{i+1}:{s}" for s in info.get("stale", []))
        cost += (info.get("usage") or {}).get("total_cost_usd") or 0
        rows.append({"turn": i + 1, "text": turn["text"], "ok_parse": info["ok"], "intended": sorted(intended),
                     "turn_ok": info["ok"] and not (intended & drift) and not new if intended else (not new and info["ok"]),
                     "drift": sorted(drift), "new_errors": sorted(new), "composer_lost": sorted(p for p in drift if any(p.startswith(q) for q in protected)),
                     "tempo_err_s": round(tempo, 3), "gold_stale": grep["stale"], "arm_stale": info.get("stale", []),
                     **{k_: info[k_] for k_ in ("error", "refused", "ops") if k_ in info}, "elapsed": round(info["elapsed"], 1), "raw": info["raw"]})
        gp, ga, mp, ma, drift_before = gp2, ga2, mp2, ma2, drift
    res = {"session": sess["id"], "arm": arm, "model": model, "draw": k, "turns": rows, "final_drift": len(rows[-1]["drift"]),
           "final_exact": not rows[-1]["drift"],
           "final_drift_lenient": len([d for d in rows[-1]["drift"] if not d.endswith(".depends_on")]), "turns_ok": sum(r["turn_ok"] for r in rows), "rejected": sum(not r["ok_parse"] for r in rows),
           "composer_lost_final": rows[-1]["composer_lost"], "stale_missed": sorted(stale_missed), "cost": round(cost, 4)}
    (out_dir / f"{sess['id']}-{arm}-d{k}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"{model} {sess['id']} {arm} d{k}: turns ok {res['turns_ok']}/8 rejected {res['rejected']} final drift {res['final_drift']} "
          f"composer lost {len(res['composer_lost_final'])} stale missed {len(stale_missed)} ${cost:.2f}", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--arms", nargs="*", default=["typed", "patch", "free", "bare"]); ap.add_argument("--only", nargs="*")
    ap.add_argument("--base-url"); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--out", default="sessions-results")
    a = ap.parse_args()
    if a.base_url:
        R.BACKEND.update(kind="openai", base_url=a.base_url)
    spec = json.load(open(E2 / "sessions.json"))
    fixtures = {n: (A.load(d / "arrangement.json"), A.load(d / "piano-analysis.json"),
                    A.load(d / "asset-catalog.json") if (d / "asset-catalog.json").exists() else None) for n, d in R.FIX.items()}
    out_dir = E2 / a.out / a.model; out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(s, arm, k) for s in spec["sessions"] if not a.only or s["id"] in a.only for arm in a.arms for k in range(1, a.draws + 1)
            if not (out_dir / f"{s['id']}-{arm}-d{k}.json").exists()]
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(run_one, s, fixtures[s["fixture"]], arm, a.model, k, out_dir) for s, arm, k in jobs]
        for f in cf.as_completed(futs):
            try:
                f.result()
            except Exception as e:
                print("job failed:", repr(e)[:300], flush=True)


if __name__ == "__main__":
    main()
