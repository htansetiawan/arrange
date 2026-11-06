#!/usr/bin/env python3
"""run_e2.py — the revision suite: typed operations versus free-form plan editing, same model, same instruction.

    python3 run_e2.py --draws 3 --model claude-sonnet-5-5 [--only a1 b2] [--dry] [--out results-new]   # writes <out>/*.json

For every instruction in instructions.json and every draw:
  C1 (typed): the model sees the plan, the operation vocabulary and the instruction, and answers with a JSON list of
      operations. revise.apply_ops applies them deterministically (validation, protected fields, derived seconds,
      stale marking); refused and unresolved operations are counted as such.
  C2 (free-form): the model sees the same plan, the same schema notes and the same instruction, and answers with the
      whole edited plan plus a list of layers it believes are now stale. The same validator runs; derived seconds are
      recomputed by the same clock so the arm is not penalised for arithmetic; stale is as the model declared.
Scoring against the gold (expected_ops applied to the frozen fixture): intended-change precision and recall over
changed paths (derived excluded), collateral paths, protected-field violations, stale-set match, unsupported handling,
validity, and the outcome class. The model is called through the claude CLI in print mode with a bare system prompt
and no tools, so each call is one completion. Nothing here is a human study.
"""
import argparse, copy, json, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

E2 = Path(__file__).resolve().parent
ROOT = E2.parents[1]
sys.path.insert(0, str(ROOT / "skills/arrange-plan/scripts"))
import arrangement as A  # noqa: E402
from clock import Clock  # noqa: E402

FIX = {"real": E2 / "real", "synthetic": E2 / "synthetic"}   # frozen copies; hashes in each folder's FROZEN.sha256

SCHEMA_NOTES = """You are helping a musician revise an arrangement plan for their own piano recording.
The plan is JSON (schema arrange/arrangement@2). What matters:
- layers[]: id (L1..), name, class, kind (generated|take|stub), route (audio|score|take|stub), anchors.enter/exit as
  {bar, beat}; exits are EXCLUSIVE (a layer that sounds through bar 40 exits at bar 41 beat 1). t0/t1 are derived
  seconds and must never be edited by hand.
- conditions.audio_context: ids (piano or earlier layers) mixed into a generated layer's input audio. A 'take' (the
  musician's own recording) and a 'stub' (silent placeholder) listen to nothing. A score-route vocal (soulx-singer)
  does not consume audio_context at all.
- candidates[]: rendered attempts; chosen: the candidate id in use. Layers whose conditions depend on a changed layer,
  or on the clock, are STALE after a change and must be re-rendered.
- owner: which fields the creator decided; the creator's decisions are never changed unless the instruction asks.
- kind 'stub' has stub_reason; a stubbed generated layer keeps its job under before_stub so it can be restored.
- The clock is the tempo map in piano-analysis.json; a downbeat correction is a change to that map, not to a layer.
Bars and beats come from the measured map: beats run 1..4 in 4/4."""

OPS_DOC = """Answer ONLY with a JSON list of operations from this vocabulary (no prose, no code fences):
  {"op":"set_entry","layer":L,"bar":n,"beat":b}   {"op":"shift_entry","layer":L,"by_bars":n}
  {"op":"set_exit","layer":L,"bar":n,"beat":b}    {"op":"shift_exit","layer":L,"by_bars":n}      (exits are exclusive)
  {"op":"set_context","layer":L,"audio_context":[ids]}   {"op":"choose_candidate","layer":L,"candidate":<id or 1-based number>}
  {"op":"set_gain","layer":L,"db":x}   {"op":"replace_with_take","layer":L,"asset":"a1"}
  {"op":"set_stub","layer":L,"reason":"..."}   {"op":"unstub","layer":L}
  {"op":"set_class","layer":L,"class":"guitar"}   {"op":"add_layer","class":c,"text":t,"enter":{bar,beat},"exit":{bar,beat}}
  {"op":"lock","layer":L}   {"op":"set_clock","bar":n,"t":seconds}   {"op":"ask","question":"..."}
L may be a layer id, name or class when unambiguous. If the instruction cannot be mapped to these operations, or is
ambiguous, answer with a single {"op":"ask","question":...} that offers the musician concrete choices. Never invent
a change the musician did not ask for. If the instruction asks for something that is already the case, say so with
the matching operation (it will be reported as a no-op)."""

FREE_DOC = """Answer ONLY with one JSON object (no prose, no code fences):
  {"plan": <the complete edited arrangement JSON>, "stale": [layer ids that must be re-rendered because of this change],
   "questions": [anything you need to ask the musician], "tempo_map_corrections": [{"bar":n,"t":seconds}] }
Edit the plan directly to carry out the instruction. Change only what the instruction asks. Do not edit t0/t1 (they are
recomputed). If the instruction cannot be carried out or is ambiguous, return the plan unchanged and put your question
in "questions". If something is already the case, return the plan unchanged and say so in "questions"."""


# C3 (bare): no ARRANGE knowledge at all. A one-line system prompt, the same plan and request, and the free arm's answer
# format with its one ARRANGE hint (t0/t1 are recomputed) removed. The format still names tempo_map_corrections and stale,
# because the answer has to be scorable; that is I/O, not schema knowledge.
BARE_SYSTEM = "You are helping a musician revise an arrangement plan for their own piano recording. The plan is JSON."
BARE_DOC = re.sub(r" Do not edit t0/t1 \(they are\s+recomputed\)\.", "", FREE_DOC)
assert BARE_DOC != FREE_DOC

BACKEND = {"kind": "claude", "base_url": None}


def call_openai(system, user, model):
    """A local OpenAI-compatible server (vLLM) with the same system prompt and message; reasoning text is dropped."""
    import urllib.request
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "max_tokens": 32000}
    req = urllib.request.Request(BACKEND["base_url"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.time()
    try:
        j = json.loads(urllib.request.urlopen(req, timeout=1800).read())
        text = j["choices"][0]["message"].get("content") or ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
        usage = {"total_cost_usd": 0.0, "tokens": j.get("usage"), "model": [model], "finish": j["choices"][0].get("finish_reason")}
    except Exception as e:
        text, usage = "", {"error": str(e)[-500:]}
    return text, usage, time.time() - t


def call_model(system, user, model):
    if BACKEND["kind"] == "openai":
        return call_openai(system, user, model)
    # the prompt goes in on stdin: a positional prompt after a variadic flag such as --disallowedTools is swallowed by it
    cmd = ["claude", "-p", "--output-format", "json", "--model", model, "--no-session-persistence",
           "--system-prompt", system, "--disallowedTools", "Bash", "Read", "Write", "Edit", "Agent", "WebFetch", "WebSearch", "Glob", "Grep"]
    t = time.time()
    # an empty folder outside any project, so the CLI loads no project instructions or memory into the call
    work = tempfile.mkdtemp(prefix="arrange-e2-")
    try:
        r = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=600, cwd=work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    el = time.time() - t
    try:
        j = json.loads(r.stdout)
        text = j.get("result", "")
        usage = {k: j.get(k) for k in ("total_cost_usd", "duration_api_ms")}
        usage["model"] = list((j.get("modelUsage") or {}).keys())
    except json.JSONDecodeError:
        text, usage = r.stdout, {"error": r.stderr[-500:]}
    return text, usage, el


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    start = min([i for i in (text.find("["), text.find("{")) if i >= 0] or [0])
    return json.loads(text[start:])


def gold_for(inst, plan, an, cat):
    ops = copy.deepcopy(inst["expected_ops"])
    for op in ops:
        if op["op"] == "set_clock" and isinstance(op.get("t"), str):
            clk = Clock(an); op["t"] = round(clk.t(op["bar"], 1)[0] - 0.5, 3)   # f1: half a second earlier, frozen from the fixture
    gp, ga, rep = A.apply_ops(plan, an, ops, actor="creator", reason="gold", catalog=cat)
    return gp, ga, rep, ops


BOOKKEEPING = re.compile(r"(^open\.questions|\.owner\.)")


def editorial(paths):
    return set(p for p in paths if not BOOKKEEPING.search(p))


def score(diff_paths, gold_paths, stale, expected_stale, plan_before, outcome, unsupported_case, protected_paths):
    gp = editorial(gold_paths)
    dp = editorial(diff_paths)
    tp = len(gp & dp)
    rec = tp / len(gp) if gp else (1.0 if not dp else 0.0)
    prec = tp / len(dp) if dp else (1.0 if not gp else 0.0)
    collateral = sorted(dp - gp)
    violated = sorted(p for p in collateral if any(p.startswith(pp) for pp in protected_paths))
    return {"recall": round(rec, 3), "precision": round(prec, 3), "collateral": collateral, "protected_violations": violated,
            "stale_match": sorted(stale) == sorted(expected_stale), "stale": sorted(stale), "expected_stale": sorted(expected_stale),
            "unsupported_ok": (outcome in ("unresolved", "no-op") and not dp) if unsupported_case else None, "outcome": outcome}


def protected(plan):
    out = []
    for L in plan["layers"]:
        for f, who in (L.get("owner") or {}).items():
            if who == "creator":
                key = {"exists": "kind", "anchors": "anchors", "route": "route", "conditions": "conditions", "prompt": "job.params.prompt", "chosen": "chosen", "gain": "gain_db"}[f]
                out.append(f"layers.{L['id']}.{key}")
    return out


def run_typed(inst, plan, an, cat, model):
    user = f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}\n\nSECTIONS: {json.dumps([{k: s[k] for k in ('label', 'bar_start', 'bar_end')} for s in plan['sections']])}\n\nTHE MUSICIAN SAYS: {inst['text']}\n\n{OPS_DOC}"
    text, usage, el = call_model(SCHEMA_NOTES, user, model)
    try:
        ops = extract_json(text)
        if isinstance(ops, dict):
            ops = [ops]
    except Exception as e:
        return {"raw": text, "usage": usage, "elapsed": el, "ops": None, "outcome": "invalid", "error": f"not JSON: {e}"}
    try:
        np_, na, rep = A.apply_ops(plan, an, ops, actor="creator", reason=inst["text"], catalog=cat)
    except Exception as e:
        return {"raw": text, "usage": usage, "elapsed": el, "ops": ops, "outcome": "invalid", "error": str(e)}
    problems = A.validate(np_, na)
    changed = editorial([c["path"] for c in rep["diff"]])
    if problems:
        outcome = "invalid"
    elif rep["unresolved"] and not changed:
        outcome = "unresolved"
    elif rep["refused"] and not changed:
        outcome = "refused"
    elif not changed:
        outcome = "no-op"
    else:
        outcome = "applied"
    return {"raw": text, "usage": usage, "elapsed": el, "ops": ops, "applied": [a["effect"] for a in rep["applied"]], "refused": rep["refused"],
            "unresolved": rep["unresolved"], "stale": rep["stale"], "diff": [c["path"] for c in rep["diff"]], "validation": problems, "outcome": outcome}


PATCH_DOC = """Answer ONLY with one JSON object (no prose, no code fences):
  {"edits": [{"path": "<dotted JSON path into the plan, layers addressed by id, e.g. layers.L2.anchors.enter.bar>", "value": <new value>}],
   "stale": [layer ids that must be re-rendered because of this change], "questions": [anything you need to ask the musician],
   "tempo_map_corrections": [{"bar": n, "t": seconds}] }
Edit only what the instruction asks; use as few edits as possible. Do not edit t0/t1 (they are recomputed). To make a layer a
silent placeholder set layers.<id>.kind and layers.<id>.route to "stub" and give layers.<id>.stub_reason. If the instruction cannot
be carried out or is ambiguous, return an empty edits list and put your question in "questions". If it is already the case,
return an empty edits list and say so in "questions"."""


def set_path(obj, path, value):
    """Set a dotted path; layers.<id>.x addresses the layer with that id; [n] indexes a list."""
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", path)
    cur = obj
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part.startswith("["):
            idx = int(part[1:-1])
            if last:
                cur[idx] = value
            else:
                cur = cur[idx]
            continue
        if isinstance(cur, list) and parts[i - 1] == "layers":
            hit = next((L for L in cur if L.get("id") == part), None)
            if hit is None:
                raise KeyError(f"no layer {part}")
            if last:
                raise KeyError("cannot replace a whole layer")
            cur = hit; continue
        if last:
            cur[part] = value
        else:
            if part not in cur:
                cur[part] = {}
            cur = cur[part]


def run_patch(inst, plan, an, cat, model):
    user = f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}\n\nSECTIONS: {json.dumps([{k: s[k] for k in ('label', 'bar_start', 'bar_end')} for s in plan['sections']])}\n\nTHE MUSICIAN SAYS: {inst['text']}\n\n{PATCH_DOC}"
    text, usage, el = call_model(SCHEMA_NOTES, user, model)
    try:
        obj = extract_json(text)
        edits = obj.get("edits") or []; stale = obj.get("stale") or []; qs = obj.get("questions") or []; corr = obj.get("tempo_map_corrections") or []
    except Exception as e:
        return {"raw": text[:4000], "usage": usage, "elapsed": el, "outcome": "invalid", "error": f"not the expected JSON: {e}"}
    new_plan = copy.deepcopy(plan); na = copy.deepcopy(an); failed = []
    for ed in edits:
        try:
            set_path(new_plan, ed["path"], ed["value"])
        except Exception as e:
            failed.append({"edit": ed, "why": str(e)})
    for c in corr:
        try:
            na = A.apply_ops(plan, na, [{"op": "set_clock", "bar": c["bar"], "t": c["t"]}], actor="creator", reason="patch")[1]
        except Exception as e:
            qs.append(f"clock correction refused: {e}")
    try:
        A.derive_times(new_plan, na)
        problems = A.validate(new_plan, na)
    except Exception as e:
        return {"raw": text[:4000], "usage": usage, "elapsed": el, "edits": edits, "outcome": "invalid", "error": str(e)}
    d = A.diff(plan, new_plan)
    paths = [c["path"] for c in d] + (["piano-analysis.json#tempo_map"] if corr else [])
    changed = editorial(paths)
    if problems or failed:
        outcome = "invalid"
    elif not changed and qs:
        outcome = "unresolved"
    elif not changed:
        outcome = "no-op"
    else:
        outcome = "applied"
    return {"raw": text[:4000], "usage": usage, "elapsed": el, "edits": edits, "failed_edits": failed, "stale": stale, "questions": qs, "diff": paths, "validation": problems, "outcome": outcome}


def run_free(inst, plan, an, cat, model, system=SCHEMA_NOTES, doc=FREE_DOC):
    user = f"PLAN:\n{json.dumps(plan, ensure_ascii=False)}\n\nSECTIONS: {json.dumps([{k: s[k] for k in ('label', 'bar_start', 'bar_end')} for s in plan['sections']])}\n\nTHE MUSICIAN SAYS: {inst['text']}\n\n{doc}"
    text, usage, el = call_model(system, user, model)
    try:
        obj = extract_json(text)
        new_plan = obj["plan"]; stale = obj.get("stale") or []; qs = obj.get("questions") or []; corr = obj.get("tempo_map_corrections") or []
    except Exception as e:
        return {"raw": text[:4000], "usage": usage, "elapsed": el, "outcome": "invalid", "error": f"not the expected JSON: {e}"}
    na = copy.deepcopy(an)
    for c in corr:   # same deterministic clock edit as the typed arm
        try:
            na = A.apply_ops(plan, na, [{"op": "set_clock", "bar": c["bar"], "t": c["t"]}], actor="creator", reason="free-form")[1]
        except Exception as e:
            qs.append(f"clock correction refused: {e}")
    try:
        A.derive_times(new_plan, na)
        problems = A.validate(new_plan, na)
    except Exception as e:
        return {"raw": text[:4000], "usage": usage, "elapsed": el, "outcome": "invalid", "error": str(e)}
    d = A.diff(plan, new_plan)
    paths = [c["path"] for c in d] + (["piano-analysis.json#tempo_map"] if corr else [])
    changed = editorial(paths)
    if problems:
        outcome = "invalid"
    elif not changed and qs:
        outcome = "unresolved"
    elif not changed:
        outcome = "no-op"
    else:
        outcome = "applied"
    return {"raw": text[:4000], "usage": usage, "elapsed": el, "stale": stale, "questions": qs, "diff": paths, "validation": problems, "outcome": outcome}


def run_bare(inst, plan, an, cat, model):
    return run_free(inst, plan, an, cat, model, system=BARE_SYSTEM, doc=BARE_DOC)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=3); ap.add_argument("--model", default="claude-sonnet-5-5")
    ap.add_argument("--only", nargs="*"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--arms", nargs="*", default=["typed", "free", "patch"])
    ap.add_argument("--out", default="results", help="results folder next to this script (one per model for the model comparison)")
    ap.add_argument("--base-url", help="use a local OpenAI-compatible server (vLLM) at this URL instead of the claude CLI")
    a = ap.parse_args()
    if a.base_url:
        BACKEND.update(kind="openai", base_url=a.base_url)
    spec = json.load(open(E2 / "instructions.json"))
    out_dir = E2 / a.out; out_dir.mkdir(parents=True, exist_ok=True)
    fixtures = {}
    for name, d in FIX.items():
        if (d / "arrangement.json").exists():
            fixtures[name] = (A.load(d / "arrangement.json"), A.load(d / "piano-analysis.json"), A.load(d / "asset-catalog.json") if (d / "asset-catalog.json").exists() else None)
    rows = []
    for inst in spec["instructions"]:
        if a.only and inst["id"] not in a.only:
            continue
        if inst["fixture"] not in fixtures:
            print(f"{inst['id']}: fixture {inst['fixture']} missing, skipped"); continue
        plan, an, cat = fixtures[inst["fixture"]]
        gp, ga, grep, gops = gold_for(inst, plan, an, cat)
        gold_paths = [c["path"] for c in grep["diff"]]
        prot = protected(plan)
        unsupported = inst["cat"] == "g" or inst["id"] == "b2"
        expected_stale = grep["stale"]
        rec = {"id": inst["id"], "cat": inst["cat"], "fixture": inst["fixture"], "text": inst["text"], "gold_ops": gops, "gold_paths": gold_paths,
               "gold_stale": expected_stale, "gold_refused": grep["refused"], "draws": {"typed": [], "free": [], "patch": [], "bare": []}}
        prev = out_dir / f"{inst['id']}.json"
        if prev.exists() and not a.dry:   # keep the arms already run; only the requested arms are (re)drawn
            old = json.loads(prev.read_text())
            for arm_, draws in old.get("draws", {}).items():
                if arm_ not in a.arms:
                    rec["draws"][arm_] = draws
        print(f"{inst['id']} [{inst['fixture']}] gold paths {len(gold_paths)} stale {expected_stale} refused {len(grep['refused'])}")
        if a.dry:
            rows.append(rec); continue
        for arm in a.arms:
            rec["draws"][arm] = []
            for k in range(a.draws):
                r = {"typed": run_typed, "free": run_free, "patch": run_patch, "bare": run_bare}[arm](inst, plan, an, cat, a.model)
                r["score"] = score(r.get("diff", []), gold_paths, r.get("stale", []), expected_stale, plan, r["outcome"], unsupported, prot)
                rec["draws"][arm].append(r)
                s = r["score"]
                print(f"   {arm} draw {k+1}: {r['outcome']:<10} recall {s['recall']} precision {s['precision']} collateral {len(s['collateral'])} stale_ok {s['stale_match']} {'(unsupported ok=' + str(s['unsupported_ok']) + ')' if unsupported else ''} {r['elapsed']:.0f}s")
        rows.append(rec)
        (out_dir / f"{inst['id']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    json.dump({"model": a.model, "draws": a.draws, "instructions": rows}, open(out_dir / "summary.json", "w"), indent=1, ensure_ascii=False)
    print("wrote", out_dir / "summary.json")


if __name__ == "__main__":
    main()
