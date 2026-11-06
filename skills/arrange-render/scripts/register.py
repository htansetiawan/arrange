#!/usr/bin/env python3
"""register.py — record a backend's candidates on a layer of arrangement.json.

    python3 register.py arrangement.json L1 build/L1/candidates.json [--provisional 1]

Adds every candidate (rendered or failed) to the layer with its parents'
hashes and measurements, sets status rendered, and marks the first rendered
one as the provisional choice unless the creator has already chosen. The
creator's choice is a revision (choose_candidate), never made here.
"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
import arrangement as A  # noqa: E402


def main():
    plan_p, lid, cands_p = sys.argv[1], sys.argv[2], sys.argv[3]
    plan = A.load(plan_p); L = A.layer_by_id(plan, lid); c = json.load(open(cands_p))
    # earlier attempts stay in the record as superseded (the trace prints every attempt); new ids continue the count
    old = L.get("candidates") or []
    for o in old:
        if o.get("status") in ("rendered", "chosen"):
            o["status"] = "superseded"
    start = max([int(o["id"][len(lid) + 1:]) for o in old if o["id"].startswith(lid + "c") and o["id"][len(lid) + 1:].isdigit()] + [0])
    L["candidates"] = list(old)
    for k, cand in enumerate(c["candidates"], start + 1):
        L["candidates"].append({"id": f"{lid}c{k}", "label": cand["id"], "status": cand["status"], "path": cand.get("path"),
                                "parents": {**cand.get("parents", {}), "clock": plan.get("clock", {}).get("revision", 0),
                                            **{x: A.layer_by_id(plan, x).get("chosen") for x in L.get("conditions", {}).get("audio_context", []) if x != "piano"}},
                                "measurements": {k2: v for k2, v in cand.items() if k2 in ("elapsed_s", "generated_s", "placed_at_s", "frames_match_spine", "peak", "rms_db", "generated_sr", "error")},
                                "backend": cand.get("backend")})
    rendered = [x for x in L["candidates"] if x["status"] == "rendered"]
    if rendered and (L.get("owner", {}).get("chosen") != "creator" or L.get("chosen") not in [x["id"] for x in rendered]):
        L["chosen"] = rendered[0]["id"]; L["owner"]["chosen"] = "claude"   # a creator choice among superseded candidates is void; they choose again
    L["status"] = "rendered" if rendered else "blocked"; L["stale"] = False; L["stale_reason"] = None
    # rendered against a parent that is itself stale, or whose chosen candidate has since changed? then stale from birth
    for x in L.get("conditions", {}).get("audio_context", []):
        if x == "piano":
            continue
        P = A.layer_by_id(plan, x); used = {c["parents"].get(x) for c in L["candidates"]}
        if P.get("stale") or (P.get("chosen") and P["chosen"] not in used):
            L["stale"], L["status"] = True, "stale"
            L["stale_reason"] = f"rendered against {x} candidate {sorted(u for u in used if u)} which is {'stale (' + str(P.get('stale_reason')) + ')' if P.get('stale') else 'no longer the chosen one (' + str(P.get('chosen')) + ')'}"
    # layers that heard this one were rendered against a candidate that is no longer the chosen one: stale
    downstream = A.mark_stale(plan, [lid], f"{lid} was re-rendered and its chosen candidate changed", self_ids=())
    A.save(plan, plan_p)
    failed = sum(1 for x in L["candidates"] if x["status"] == "failed"); superseded = sum(1 for x in L["candidates"] if x["status"] == "superseded")
    print(f"{lid}: {len(rendered)} rendered, {failed} failed, {superseded} superseded; provisional choice {L.get('chosen')} (the creator decides)" + (f"; now stale: {downstream}" if downstream else ""))


if __name__ == "__main__":
    main()
