#!/usr/bin/env python3
"""rescore.py — rescore the stored answers after a per-item diagnosis, as the composer decided:

1. answers the record itself accepts count (acceptable_alternatives / tolerance, which the first scorer missed):
   cp-layer-pitches 'walls' for 'wall'; cp-redbrick-melisma 'walls' F4 + a held F4 instead of one long F4;
   cp-bar18-assign the second F5 after 'hush' unsung instead of held;
   cp-layer-words any split on the old beats with every syllable on its own note; sd-grace-fold 'hall' and 'mor'
   each on a singable note (>= 0.2 s), the grace note folded, unsung or held; sd-hall-g4 a sung G4 (held 'hall' or a
   new syllable) from his A4 release (or later) to the next phrase.
2. where the request did not pin down one edit (INCOMPLETE, from the diagnosis), a question counts as correct when the
   edits made alongside it agree with his fix (no change contradicts it). Only the typed arm has an ask operation, so
   'edit or justified question' is reported for typed only; the arm comparison uses 'edit only'.

    python3 rescore.py            # -> RESCORE.md

Without the fits (items/ is not distributed) it writes RESCORE.md from rescored-draws.json, the per-try outcomes that
paper_numbers.py stored when it was run with them.
"""
import copy, json, re
from pathlib import Path
import run_lyrics as L
import run_e2 as R

HERE = Path(__file__).resolve().parent
INCOMPLETE = {"cp-bar18-assign", "cp-redbrick-melisma", "cp-layer-words", "cp-footsteps-sounds", "sd-grace-fold", "sd-hall-g4"}

_alt0, _custom0 = L.alt_golds, L.custom


def alt_golds(it):
    G = it["after"]["rows"]; out = list(_alt0(it))
    if it["id"] == "cp-layer-pitches":
        A = copy.deepcopy(G)
        for r in A:
            if (r.get("text") or "").lower() == "wall":
                r.update(text="walls", word="walls")
        out.append(A)
    if it["id"] == "cp-redbrick-melisma":   # 'walls' F4 + held F4 (the two F4s kept) instead of one long F4
        A = copy.deepcopy(G); k = next(i for i, r in enumerate(A) if (r.get("text") or "").lower() == "walls")
        end = A[k]["end"]; A[k]["end"] = 56.654
        A.insert(k + 1, {**A[k], "t": 56.654, "end": end, "kind": "slur", "text": "~"})
        out.append(A)
        for B in (copy.deepcopy(G), copy.deepcopy(A)):   # 'wall' as he wrote it
            for r in B:
                if (r.get("text") or "").lower() == "walls":
                    r.update(text="wall", word="wall")
            out.append(B)
    if it["id"] == "cp-bar18-assign":   # the second F5 after 'hush' left unsung
        A = copy.deepcopy(G)
        for i, r in enumerate(A):
            if r["pitch"] == 77 and r.get("kind") == "slur" and i and (A[i - 1].get("text") or "").lower() == "hush":
                r.update(kind="unsung", text="", word=None)
        out.append(A)
    return out


def custom(it, rows, Sm):
    B = it["before"]["rows"]
    if it["id"] == "cp-layer-words":   # every syllable its own note, in order, on the old beats; nothing outside moved
        span = (53.9, 57.97)
        out_m = [r for r in rows if not (span[0] <= r["t"] < span[1])]; out_b = [r for r in B if not (span[0] <= r["t"] < span[1])]
        if len(out_m) != len(out_b) or any(not L.same(a, b, 0.02, 0.02, word=False) for a, b in zip(sorted(out_m, key=lambda r: r["t"]), out_b)):
            return False
        ins = sorted([r for r in rows if span[0] <= r["t"] < span[1]], key=lambda r: r["t"])
        syl = [L.norm_text(r) for r in ins]
        if syl != ["to", "the", "la", "yer", "of", "red", "brick", "walls"] or any(r.get("kind") != "note" for r in ins):
            return False
        old = [r for r in B if span[0] <= r["t"] < span[1]]
        def inside(r):   # starts inside an old note and keeps that note's pitch
            return any(o["t"] - 0.03 <= r["t"] < o["end"] and L.to_midi(r["pitch"]) == o["pitch"] for o in old)
        return all(inside(r) for r in ins) and abs(ins[0]["t"] - old[0]["t"]) < 0.03 and abs(ins[-1]["end"] - old[-1]["end"]) < 0.05
    if it["id"] == "sd-grace-fold":
        wins = [(17.84, 18.47, "hall"), (37.12, 37.70, "mor")]
        inw = lambda r: any(a <= r["t"] < b for a, b, _ in wins)
        om = sorted([r for r in rows if not inw(r)], key=lambda r: r["t"])
        def eq(X):   # outside the two places: unchanged, or with the other three grace notes folded as he also did
            return len(om) == len(X) and all(L.same(a, b, 0.02, 0.02, word=False) for a, b in zip(om, X))
        if not (eq([r for r in B if not inw(r)]) or eq([r for r in it["after"]["rows"] if not inw(r)])):
            return False
        for a, b, syl in wins:
            w = [r for r in rows if a <= r["t"] < b]
            sung = [r for r in w if r.get("kind") == "note"]
            if len(sung) != 1 or L.norm_text(sung[0]) != syl or sung[0]["end"] - sung[0]["t"] < 0.2:
                return False
        return True
    if it["id"] == "sd-hall-g4":
        new = [r for r in rows if L.to_midi(r["pitch"]) == 67 and 18.47 <= r["t"] and r["end"] <= 19.33]
        rest = [r for r in rows if r not in new]
        g = new[0] if len(new) == 1 else None   # sung: a hold of 'hall', or a note with its own syllable
        if g is None or not ((g.get("kind") == "slur" and (g.get("word") or "hall").lower() in ("hall", "hallway"))
                             or (g.get("kind") == "note" and L.norm_text(g) not in ("", "~"))):
            return False
        if len(rest) != len(B):
            return False
        for a, b in zip(sorted(rest, key=lambda r: r["t"]), B):
            if (b.get("text") or "").lower() == "hall":
                if not (L.same(a, b, 0.02, 1.0, word=False) and a["end"] <= new[0]["t"] + 0.02):
                    return False
            elif not L.same(a, b, 0.02, 0.02, word=False):
                return False
        return True
    return _custom0(it, rows, Sm)


L.alt_golds, L.custom = alt_golds, custom
_score0 = L.score


def score(it, rows, pron):
    s = _score0(it, rows, pron)
    if it["id"] in ("cp-layer-words", "sd-grace-fold", "sd-hall-g4"):   # these rules decide alone (collateral is part of them)
        c = custom(it, rows, None)
        s["correct"] = s["request_done"] = bool(c)
    return s


def consistent(it, rows, pron):
    """Edits made beside a question must agree with his fix: every changed row equals a gold row, nothing the gold
    keeps is deleted, and no syllable's sounds change to something other than the gold's."""
    B, G = it["before"]["rows"], it["after"]["rows"]
    golds = [G] + alt_golds(it)
    mb = dict(L.align(rows, B))
    for i, m in enumerate(rows):
        if i in mb and L.same(m, B[mb[i]], 0.02, 0.02, word=False):
            continue
        ok = any(L.same(m, GG[j], 0.06, 0.12, word=False) for GG in golds for _, j in L.align([m], GG))
        if not ok:
            return False
    bg = {j for j, _ in L.align(B, G)}
    for j in range(len(B)):
        if j not in set(mb.values()) and j in bg:
            return False
    if it["cat"] == "phoneme" and pron != it["pron_before"]:
        Sm = L.sounds(rows, pron, it["phon"]); Sb = L.sounds(B, it["pron_before"], it["phon"], key=f"{it['id']}-before")
        Sg = L.sounds(G, it["pron_after"], it["phon"], key=f"{it['id']}-after")
        if len(Sm) != len(Sb) or len(Sg) != len(Sb):
            return False
        st = lambda p: re.sub(r"2", "1", p or "")
        if any(st(Sm[k][1]) != st(Sb[k][1]) and st(Sm[k][1]) != st(Sg[k][1]) for k in range(len(Sb))):
            return False
    return True


def rescore_one(it, arm, d):
    text = d.get("raw", "")
    try:
        obj = R.extract_json(text)
        if arm == "typed":
            obj = [obj] if isinstance(obj, dict) else obj
            rows, pron, asked = L.apply_typed(it, obj)
        else:
            rows, pron, asked = L.apply_rewrite(obj, it, arm)
        s = score(it, rows, pron)
        edit_ok = bool(s["correct"])
        ask_ok = bool(asked) and not edit_ok and it["id"] in INCOMPLETE and consistent(it, rows, pron)
        return {"edit": edit_ok, "ask": ask_ok, "asked": bool(asked), "invalid": False}
    except Exception as e:  # noqa: BLE001
        return {"edit": False, "ask": False, "asked": False, "invalid": True, "err": str(e)[:200]}


def main():
    """One record per stored answer (model, arm, item, category, first scoring, rescored outcome), then RESCORE.md."""
    recs, cats_of = [], {}
    if not (HERE / "items").exists():   # the fits are not distributed: the per-try outcomes paper_numbers.py stored
        for d in json.load(open(HERE / "rescored-draws.json")):
            cats_of.setdefault(d["item"], d["cat"])
            recs.append((d["model"], d["arm"], d["item"], d["outcome_stored"] == "correct", d))
    else:
        its = {i["id"]: i for i in L.items()}
        cats_of = {i: it["cat"] for i, it in its.items()}
        for f in sorted((HERE / "results").glob("*.json")):
            res = json.load(open(f)); m = res["model"]
            for r in res["rows"]:
                if r["id"] not in its:
                    continue
                for arm, D in r["draws"].items():
                    for d in D:
                        if L.LIMIT.search(d.get("raw", "")[:300]):
                            continue
                        recs.append((m, arm, r["id"], bool(d["score"].get("correct")), rescore_one(its[r["id"]], arm, d)))
    write(recs, cats_of)


def write(recs, cats_of):
    old, new = {}, {}
    for m, arm, i, o, x in recs:
        old.setdefault((m, arm), []).append((i, o)); new.setdefault((m, arm), []).append((i, x))
    n_it = len(cats_of)
    cats = [c for c in ("timing", "fitting", "phoneme", "words") if c in cats_of.values()]
    lines = [f"# E2-lyrics rescored (rescore.py; {n_it} items)", "",
             "accepted = edit matches his fix or an answer the record accepts; + question = also a question where the request did not pin down one edit "
             f"(typed arm only: only it has an ask operation). old = the first scoring, same {n_it} items.", "",
             "| model | arm | old | accepted | + question (typed) | " + " | ".join(cats) + " | invalid |", "|---" * (6 + len(cats)) + "|"]
    per_item = {}
    for (m, arm), X in sorted(new.items()):
        o = old[(m, arm)]; n = len(X)
        acc = sum(x["edit"] for _, x in X) / n; withq = sum(x["edit"] or x["ask"] for _, x in X) / n
        pc = lambda c: (lambda S: f"{sum(x['edit'] for _, x in S)}/{len(S)}")([(i, x) for i, x in X if cats_of[i] == c])
        lines.append(f"| {m} | {arm} | {sum(c for _, c in o) / len(o):.2f} | {acc:.2f} | {withq:.2f} |" if arm == "typed" else
                     f"| {m} | {arm} | {sum(c for _, c in o) / len(o):.2f} | {acc:.2f} | - |")
        lines[-1] += "".join(f" {pc(c)} |" for c in cats) + f" {sum(x['invalid'] for _, x in X)} |"
        for i, x in X:
            per_item.setdefault(i, {}).setdefault((m, arm), []).append(x)
    lines += ["", "## Per item, Claude typed (Haiku + Sonnet + Opus, 9 tries): old / accepted / + question", "",
              "| item | cat | request pinned one edit? | old | accepted | + question |", "|---|---|---|---|---|---|"]
    for i, cat in cats_of.items():
        cl = [(m, a) for (m, a) in per_item.get(i, {}) if m.startswith("claude") and a == "typed"]
        xs = [x for k in cl for x in per_item[i][k]]
        ol = [c for k in cl for j, c in old[k] if j == i]
        lines.append(f"| {i} | {cat} | {'no' if i in INCOMPLETE else 'yes'} | {sum(ol)}/{len(ol)} | {sum(x['edit'] for x in xs)}/{len(xs)} | {sum(x['edit'] or x['ask'] for x in xs)}/{len(xs)} |")
    (HERE / "RESCORE.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    main()
