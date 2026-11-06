#!/usr/bin/env python3
"""skill_arm.py — E2-edits, third arm: Claude Code with the lyric skill installed as a Claude skill, against the
prompt arm ('typed', same notes and edit vocabulary given in the prompt) and the raw rows ('bare').

Each try runs in a fresh folder outside the repo (no AGENTS.md, CLAUDE.md or project memory):
    .claude/skills/arrange-lyrics/   SKILL.md + scripts (show_fit.py, edit_fit.py; same notes and edits as the prompt arm)
    song/fit.json, pronounce.json, clock.json, screenshot.png (when the request has one)
Claude Code runs headless with its own system prompt and the request as the composer typed it; tools: Skill, Read,
Glob, Grep, Bash(python3 ...). The fit left in song/ is scored with the same scorer as the other arms. A reply with a
question mark counts as a question (as the 'ask' edit does in the prompt arm).

    python3 skill_arm.py --model claude-sonnet-5-5 [--draws 1] [--only cp01 ...]
    python3 skill_arm.py --table          # results-skill/TABLE.md: skill vs typed vs bare, same items and draws
"""
import argparse, json, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.argv_saved = list(sys.argv); sys.argv = sys.argv[:1]
import suite  # noqa: E402
sys.argv = sys.argv_saved
L = suite.L
SKILL = HERE / "skill_arm/arrange-lyrics"; RES = HERE / "results-skill"


def sandbox(it, C):
    D = Path(tempfile.mkdtemp(prefix="arrange-song-"))
    shutil.copytree(SKILL, D / ".claude/skills/arrange-lyrics", ignore=shutil.ignore_patterns("__pycache__"))
    S = D / "song"; S.mkdir()
    rows = [{k: r.get(k) for k in ("t", "end", "pitch", "text", "word", "kind", "bar", "beat", "num")} for r in it["before"]]
    json.dump({"title": it["title"], "ts": it["ts"], "rows": rows}, open(S / "fit.json", "w"), indent=1, ensure_ascii=False)
    json.dump(it["pron_before"], open(S / "pronounce.json", "w"), indent=1, ensure_ascii=False)
    json.dump(C[it["song"]], open(S / "clock.json", "w"))
    if it.get("image_path"):
        shutil.copy(it["image_path"], S / "screenshot.png")
    return D


def request(it):
    req = (f"EARLIER IN THIS SESSION:\n{it['history']}\n\n" if it.get("history") else "") + it["request"]
    if it.get("image_path"):
        req += "\n\n(screenshot of the score canvas attached: song/screenshot.png; the red circles are mine)"
    return req


def one(it, model, C):
    D = sandbox(it, C)
    cmd = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model, "--no-session-persistence",
           "--strict-mcp-config", "--max-turns", "30", "--tools", "Skill", "Read", "Glob", "Grep", "Bash", "--allowedTools", "Skill", "Read", "Glob", "Grep", "Bash(python3:*)"]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=request(it), capture_output=True, text=True, timeout=1200, cwd=str(D))
        out = r.stdout
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
    el = round(time.time() - t0, 1)
    tools, final = [], {}
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "assistant":
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    inp = c.get("input", {})
                    tools.append(c["name"] + (":" + (inp.get("skill") or inp.get("command", "")[:90] or inp.get("file_path", ""))))
        elif ev.get("type") == "result":
            final = ev
    text = final.get("result") or ""
    if L.LIMIT.search(text[:300]) and not final.get("total_cost_usd"):
        shutil.rmtree(D, ignore_errors=True)
        raise L.LimitHit(text[:200])
    try:
        fit = json.load(open(D / "song/fit.json")); pron = json.load(open(D / "song/pronounce.json"))
        rows = [{k: r[k] for k in ("t", "end", "pitch", "text", "word", "kind")} for r in fit["rows"]]
        asked = [text] if (it["kind"] == "question" or "?" in text) else []
        s = suite.score(it, rows, pron, asked)
    except Exception as e:  # noqa: BLE001
        s = {"correct": False, "outcome": "invalid", "error": str(e)[:300]}
    if not final:
        s = {"correct": False, "outcome": "invalid", "error": "no result (timeout or crash): " + (r.stderr[-200:] if 'r' in dir() else "")}
    shutil.rmtree(D, ignore_errors=True)
    used = any(t.startswith("Skill:") for t in tools) or any("SKILL.md" in t for t in tools)
    return {"arm": "skill", "score": s, "answer": text[:4000], "tools": tools, "used_skill": used, "turns": final.get("num_turns"),
            "cost": final.get("total_cost_usd", 0), "elapsed": el}


def run(a):
    its = suite.load(); C = json.load(open(suite.BUILD / "clocks.json")); RES.mkdir(exist_ok=True)
    if a.only:
        its = [i for i in its if i["id"] in a.only]
    f = RES / f"{a.model}.json"
    res = json.load(open(f)) if f.exists() else {"model": a.model, "rows": {}}
    for it in its:
        have = res["rows"].setdefault(it["id"], {}).setdefault("skill", [])
        while len(have) < a.draws:
            d = one(it, a.model, C); have.append(d); json.dump(res, open(f, "w"), indent=1)
            print(f"{a.model} {it['id']} skill: {d['score']['outcome']} skill={'yes' if d['used_skill'] else 'NO'} turns={d['turns']} "
                  f"${d['cost'] or 0:.3f} {d['elapsed']}s", flush=True)


def table():
    from math import comb
    its = {i["id"]: i for i in suite.load()}
    sign_p = lambda b, w: min(1.0, 2 * sum(comb(b + w, k) for k in range(min(b, w) + 1)) / 2 ** (b + w)) if b + w else 1.0
    out = ["# E2-edits: the lyric skill installed as a Claude skill vs the same content in the prompt", "",
           "Same items; skill = Claude Code with the skill installed; typed = notes, table and edits in the prompt (one turn); "
           "bare = raw rows. Paired by item over the items the skill arm has run; typed and bare use their first draws to match.", "",
           "| model | items | skill | typed | bare | skill vs typed (items better/worse, sign-test p) | skill loaded | turns (median) | $ per try |",
           "|---|---|---|---|---|---|---|---|---|"]
    pool = {a: [0, 0, 0, 0] for a in ("skill", "typed", "bare")}   # asked on complete, complete tries, asked on incomplete, incomplete tries
    kinds_out = []
    for f in sorted(RES.glob("claude-*.json")):
        sk = json.load(open(f))["rows"]; base = json.load(open(HERE / "results" / f.name))["rows"]
        ids = [i for i in sk if sk[i].get("skill") and base.get(i, {}).get("typed") and base.get(i, {}).get("bare")]
        n = min(len(sk[i]["skill"]) for i in ids) if ids else 0
        arms = {"skill": {i: sk[i]["skill"][:n] for i in ids}, "typed": {i: base[i]["typed"][:n] for i in ids},
                "bare": {i: base[i]["bare"][:n] for i in ids}}
        rate = {a: {i: sum(x["score"]["correct"] for x in D[i]) / max(1, len(D[i])) for i in ids} for a, D in arms.items()}
        tries = [x for i in ids for x in arms["skill"][i]]
        turns = sorted(x.get("turns") or 0 for x in tries)
        better = sum(rate["skill"][i] > rate["typed"][i] for i in ids); worse = sum(rate["skill"][i] < rate["typed"][i] for i in ids)
        m = lambda d: sum(d.values()) / max(1, len(d))
        out.append(f"| {f.stem} | {len(ids)} x {n} | {m(rate['skill']):.2f} | {m(rate['typed']):.2f} | {m(rate['bare']):.2f} | "
                   f"{better}/{worse}, p = {sign_p(better, worse):.3f} | {sum(x['used_skill'] for x in tries)}/{len(tries)} | "
                   f"{turns[len(turns) // 2] if turns else '-'} | {sum(x['cost'] or 0 for x in tries) / max(1, len(tries)):.3f} |")
        for a, D in arms.items():
            for i in ids:
                if its[i]["kind"] == "question":
                    continue
                asked = sum(x["score"]["outcome"] == "asked" for x in D[i])
                k = 0 if its[i]["complete"] else 2
                pool[a][k] += asked; pool[a][k + 1] += len(D[i])
        kinds = {}
        for i in ids:
            v = kinds.setdefault(its[i]["kind"], [0, 0, 0, 0])
            v[0] += rate["skill"][i]; v[1] += rate["typed"][i]; v[2] += rate["bare"][i]; v[3] += 1
        kinds_out.append(f"- {f.stem}: " + "; ".join(f"{k} {v[0] / v[3]:.2f} / {v[1] / v[3]:.2f} / {v[2] / v[3]:.2f} (n={v[3]})" for k, v in sorted(kinds.items())))
    out += ["", "By kind, skill / typed / bare:", ""] + kinds_out
    out += ["", "Questions, pooled over the Claude models:", "",
            "| arm | asked on complete requests | asked on incomplete requests |", "|---|---|---|"]
    out += [f"| {a} | {v[0]}/{v[1]} | {v[2]}/{v[3]} |" for a, v in pool.items()]
    (RES / "TABLE.md").write_text("\n".join(out) + "\n"); print("\n".join(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model"); ap.add_argument("--draws", type=int, default=1); ap.add_argument("--only", nargs="*")
    ap.add_argument("--table", action="store_true"); a = ap.parse_args()
    table() if a.table else run(a)
