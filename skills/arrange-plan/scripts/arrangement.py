#!/usr/bin/env python3
"""arrangement.py — the plan library shared by bind, build, validate, revise and tracks.

Schema `arrange/arrangement@2`. What changed from @1 and why:

- `conditions` replaces the single `hears` list. A backend consumes only what
  it declares: `audio_context` (ids mixed into the input audio), `score_condition`
  (a melody or score the job follows), `voice_reference` (timbre), and
  `depends_on` (everything the job's result depends on, including the clock).
  A single `hears` list implied that every model listens the same way; SoulX does
  not consume an accompaniment mix at all.
- `owner` records who decided each editable field: exists, anchors, route,
  conditions, prompt, chosen. A whole-layer `chosen_by` hid mixed decisions.
- `candidates` and `chosen` keep every rendered attempt with its parents'
  hashes, so a change upstream can mark exactly the descendants that are stale.
- Intervals are half-open; `t0`/`t1` are derived by clock.py and never edited.
- `revision` counts applied changes; every applied change is written to
  `history` with its operations, actor, reason and the paths it touched.
"""
import copy, hashlib, json, math, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clock import Clock, ClockError  # noqa: E402

SCHEMA = "arrange/arrangement@2"
CLASSES = ["vocals", "backing vocals", "drums", "bass", "guitar", "keyboard", "percussion", "strings", "synth", "fx", "brass", "woodwinds"]
SUSTAINED = {"strings", "synth", "fx", "brass", "woodwinds", "keyboard"}
RHYTHMIC = {"drums", "percussion", "bass", "guitar"}
BACKENDS = {
    "soulx-singer": {"classes": {"vocals", "backing vocals"}, "consumes": {"score_condition", "voice_reference"}, "route": "score"},
    "ace-step/lego": {"classes": set(CLASSES) - {"vocals", "backing vocals"}, "consumes": {"audio_context"}, "route": "audio"},
    "take": {"classes": set(CLASSES), "consumes": set(), "route": "take"},
    "stub": {"classes": set(CLASSES) | {None}, "consumes": set(), "route": "stub"},
}
OWNED_FIELDS = ("exists", "anchors", "route", "conditions", "prompt", "chosen", "gain")
DERIVED_PATHS = re.compile(r"(\.t0$|\.t1$|^revision$|^history|^updated_at$|^clock\.|\.stale$|\.stale_reason$|\.status$|\.before_stub\.)")


class PlanError(Exception):
    pass


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(obj, path):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def layer_by_id(plan, lid):
    for L in plan["layers"]:
        if L["id"] == lid:
            return L
    raise PlanError(f"no layer {lid!r}; layers are {[x['id'] + ' (' + x['name'] + ')' for x in plan['layers']]}")


def find_layer(plan, ref):
    """Find a layer by id, name or class (case-insensitive). Ambiguity is an error with the choices listed."""
    r = str(ref).strip().lower()
    hits = [L for L in plan["layers"] if L["id"].lower() == r]
    if not hits:
        hits = [L for L in plan["layers"] if L["name"].lower() == r or L.get("class", "").lower() == r]
    if not hits:
        hits = [L for L in plan["layers"] if r in L["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise PlanError(f"no layer called {ref!r}; layers are {[x['id'] + ' (' + x['name'] + ')' for x in plan['layers']]}")
    raise PlanError(f"{ref!r} matches several layers: {[x['id'] + ' (' + x['name'] + ')' for x in hits]}")


# ---- derived times ----------------------------------------------------------
def derive_times(plan, analysis):
    clk = Clock(analysis)
    problems = []
    for s in plan.get("sections", []):
        try:
            s["t0"] = round(clk.t(s["bar_start"], 1)[0], 3)
        except ClockError as e:
            problems.append(f"section {s.get('label')}: {e}"); continue
        try:
            s["t1"] = round(clk.bar_end(s["bar_end"])[0], 3); s.pop("ends_past_map", None)
        except ClockError:
            s["t1"] = round(clk.end()[0], 3); s["ends_past_map"] = True   # the last section may run past the last tracked beat
    for L in plan["layers"]:
        a = L["anchors"]
        try:
            L["t0"] = round(clk.t(a["enter"]["bar"], a["enter"]["beat"])[0], 3)
            L["t1"] = round(clk.t(a["exit"]["bar"], a["exit"]["beat"])[0], 3)
        except ClockError as e:
            problems.append(f"layer {L['id']} ({L['name']}): {e}")
    plan["clock"] = {"from": plan.get("inputs", {}).get("analysis", "piano-analysis.json") + "#tempo_map",
                     "status": analysis.get("tempo_map", {}).get("method", "measured"),
                     "revision": analysis.get("tempo_map", {}).get("revision", 0),
                     "time_signature": clk.ts, "intervals": "half-open: exit is the first position not sounding",
                     "domain_end_s": round(clk.end()[0], 3)}
    return problems


# ---- validation -------------------------------------------------------------
def validate(plan, analysis):
    """Mechanical checks only. Returns a list of problems (strings); empty means valid."""
    p = []
    if plan.get("schema") != SCHEMA:
        p.append(f"schema is {plan.get('schema')!r}, expected {SCHEMA!r}")
    try:
        clk = Clock(analysis)
    except ClockError as e:
        return [f"clock: {e}"]
    ids = [L["id"] for L in plan["layers"]]
    if len(set(ids)) != len(ids):
        p.append("duplicate layer ids")
    order = plan.get("order", [])
    if sorted(order) != sorted(ids):
        p.append(f"order {order} does not list every layer exactly once ({ids})")
    seen = {"piano"}
    for lid in order:
        L = layer_by_id(plan, lid)
        a = L.get("anchors") or {}
        for k in ("enter", "exit"):
            if k not in a:
                p.append(f"{lid}: missing {k} anchor"); continue
            try:
                clk.validate_position(a[k]["bar"], a[k]["beat"])
                t, flags = clk.t(a[k]["bar"], a[k]["beat"])
                if abs(t - L.get("t0" if k == "enter" else "t1", math.nan)) > 1e-3:
                    p.append(f"{lid}: {('t0' if k == 'enter' else 't1')}={L.get('t0' if k == 'enter' else 't1')} disagrees with the clock ({t:.3f}); seconds are derived, rebuild")
            except (ClockError, KeyError, TypeError) as e:
                p.append(f"{lid}: {k} anchor {a.get(k)}: {e}")
        if L.get("t0") is not None and L.get("t1") is not None and not L["t0"] < L["t1"]:
            p.append(f"{lid}: enters at {L['t0']} and exits at {L['t1']}; a layer must exit after it enters")
        route, kind = L.get("route"), L.get("kind")
        if route not in ("audio", "score", "take", "stub"):
            p.append(f"{lid}: route {route!r} unknown")
        if kind not in ("generated", "take", "stub"):
            p.append(f"{lid}: kind {kind!r} unknown")
        if (route == "stub") != (kind == "stub") or (route == "take") != (kind == "take"):
            p.append(f"{lid}: route {route!r} and kind {kind!r} disagree")
        if kind == "stub" and not L.get("stub_reason"):
            p.append(f"{lid}: a stub needs a reason")
        if kind == "take" and not L.get("asset"):
            p.append(f"{lid}: a take needs an asset id")
        if kind == "generated":
            be = (L.get("job") or {}).get("backend")
            if be not in BACKENDS:
                p.append(f"{lid}: backend {be!r} unknown")
            elif L.get("class") not in BACKENDS[be]["classes"]:
                p.append(f"{lid}: class {L.get('class')!r} is not supported by {be}")
            elif BACKENDS[be]["route"] != route:
                p.append(f"{lid}: backend {be} serves route {BACKENDS[be]['route']!r}, layer says {route!r}")
            cond = L.get("conditions") or {}
            for ref in cond.get("audio_context", []):
                if ref not in seen:
                    p.append(f"{lid}: audio_context {ref!r} is not the piano or a layer earlier in order")
            if be in BACKENDS and cond.get("audio_context") and "audio_context" not in BACKENDS[be]["consumes"]:
                p.append(f"{lid}: {be} does not consume audio_context, but {cond['audio_context']} is declared")
            if be == "soulx-singer" and not cond.get("score_condition"):
                p.append(f"{lid}: a sung layer needs a score_condition")
        if L.get("chosen") and L["chosen"] not in [c["id"] for c in L.get("candidates", [])]:
            p.append(f"{lid}: chosen candidate {L['chosen']!r} does not exist")
        own = L.get("owner") or {}
        for f in OWNED_FIELDS:
            if own.get(f) not in ("creator", "claude", None):
                p.append(f"{lid}: owner.{f} = {own.get(f)!r}")
        seen.add(lid)
    return p


# ---- diffs --------------------------------------------------------------------
def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else k))
    elif isinstance(obj, list):
        if all(not isinstance(v, (dict, list)) for v in obj):
            out[prefix] = json.dumps(obj)      # a list of scalars is one value, not n paths
        else:
            for i, v in enumerate(obj):
                out.update(flatten(v, f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out


def layer_paths(plan):
    """Rewrite list indexes of layers as ids so diffs are stable: layers[2].x -> layers[L3].x."""
    out = copy.deepcopy(plan)
    out["layers"] = {L["id"]: L for L in plan["layers"]}
    return out


def diff(a, b, *, ignore_derived=True):
    fa, fb = flatten(layer_paths(a)), flatten(layer_paths(b))
    changed = []
    for k in sorted(set(fa) | set(fb)):
        if ignore_derived and DERIVED_PATHS.search(k):
            continue
        if fa.get(k, "<absent>") != fb.get(k, "<absent>"):
            changed.append({"path": k, "before": fa.get(k, "<absent>"), "after": fb.get(k, "<absent>")})
    return changed


# ---- staleness ----------------------------------------------------------------
def mark_stale(plan, changed_ids, reason, *, self_ids=()):
    """Mark as stale every layer whose rendered candidates depended on a changed layer (and the layers in
    self_ids, whose own renders are invalid). Returns the ids marked."""
    marked = []
    changed, self_ids = set(changed_ids), set(self_ids)
    for lid in plan["order"]:
        L = layer_by_id(plan, lid)
        deps = set((L.get("conditions") or {}).get("depends_on", []))
        hit = (lid in self_ids) or (deps & changed)
        if hit and L.get("candidates"):
            if not L.get("stale"):
                L["stale"] = True
                L["stale_reason"] = reason if lid in self_ids else f"{reason}; this layer was rendered against {sorted(deps & changed)}"
                L["status"] = "stale"
                marked.append(lid)
            changed.add(lid)   # descendants of a stale layer are stale too
    return marked


# ---- typed operations ----------------------------------------------------------
OPS = ("set_entry", "shift_entry", "set_exit", "shift_exit", "set_context", "choose_candidate", "set_gain",
       "replace_with_take", "set_stub", "unstub", "set_class", "add_layer", "lock", "set_clock", "ask")


def _pos(d, default_beat=1):
    return {"bar": int(d["bar"]), "beat": float(d.get("beat", default_beat))}


def apply_ops(plan, analysis, ops, *, actor="creator", reason="", catalog=None):
    """Apply typed operations deterministically. Returns (plan, analysis, report).

    report: applied (op + paths touched), refused (op + why), unresolved (questions),
    stale (ids), diff (paths changed, derived excluded).
    """
    before = copy.deepcopy(plan)
    plan, analysis = copy.deepcopy(plan), copy.deepcopy(analysis)
    clk = Clock(analysis)
    applied, refused, unresolved, changed_ids, rerender = [], [], [], set(), set()
    map_changed, clock_spans = False, []

    def own(L, field):
        L.setdefault("owner", {})[field] = actor

    for op in ops:
        name = op.get("op")
        try:
            if name not in OPS:
                raise PlanError(f"unknown operation {name!r}; allowed: {OPS}")
            if name == "ask":
                unresolved.append(op.get("question") or "(empty question)")
                applied.append({"op": op, "effect": "recorded as an open question; nothing changed"})
                continue
            if name == "set_clock":
                bar = int(op["bar"]); t_new = float(op["t"])
                beats = analysis["tempo_map"]["beats"]
                idx = next((i for i, b in enumerate(beats) if b["bar"] == bar and b["beat"] == 1), None)
                if idx is None:
                    raise PlanError(f"bar {bar} has no downbeat in the map")
                lo = max(0, idx - clk.bpb); hi = min(len(beats) - 1, idx + clk.bpb)
                if not (beats[lo]["t"] < t_new < beats[hi]["t"]) if (lo < idx < hi) else False:
                    raise PlanError(f"new downbeat {t_new}s for bar {bar} must lie between {beats[lo]['t']}s and {beats[hi]['t']}s")
                old = beats[idx]["t"]
                touched = (min(beats[lo]["t"], old, t_new), max(beats[hi]["t"], old, t_new))   # the time span whose beats move
                for i in range(lo + 1, idx):   # re-space the beats before, linearly
                    f = (i - lo) / (idx - lo); beats[i]["t"] = round(beats[lo]["t"] + f * (t_new - beats[lo]["t"]), 6)
                beats[idx]["t"] = t_new
                for i in range(idx + 1, hi):
                    f = (i - idx) / (hi - idx); beats[i]["t"] = round(t_new + f * (beats[hi]["t"] - t_new), 6)
                tm = analysis["tempo_map"]
                tm.setdefault("corrections", []).append({"bar": bar, "beat": 1, "t": t_new, "was": old, "source": actor, "scope": f"beats between bar {beats[lo]['bar']}:{beats[lo]['beat']} and {beats[hi]['bar']}:{beats[hi]['beat']} re-spaced"})
                tm["inspection"] = "creator-checked" if actor == "creator" else tm.get("inspection", "auto")
                tm["revision"] = int(tm.get("revision", 0)) + 1
                clk = Clock(analysis); map_changed = True
                clock_spans.append(touched)
                applied.append({"op": op, "effect": f"bar {bar} downbeat {old}s -> {t_new}s; beats between {touched[0]:.3f}s and {touched[1]:.3f}s re-spaced; map revision {tm['revision']}"})
                continue
            if name == "add_layer":
                lid = "L%d" % (max([int(x["id"][1:]) for x in plan["layers"] if x["id"][1:].isdigit()] + [0]) + 1)
                cls = op.get("class")
                if cls not in CLASSES:
                    raise PlanError(f"class {cls!r} is not one of {CLASSES}")
                route = op.get("route") or ("score" if cls in ("vocals", "backing vocals") else "audio")
                L = new_layer(lid, op.get("name") or cls, cls, op.get("text", ""), _pos(op["enter"]), _pos(op["exit"]), route,
                              from_={"cell": op.get("cell"), "component": None, "raw": f"<{op.get('name') or cls}: {op.get('text', '')}>"},
                              analysis=analysis)
                for f in OWNED_FIELDS:
                    L["owner"][f] = actor
                plan["layers"].append(L); plan["order"].append(lid)
                default_conditions(plan, L)
                changed_ids.add(lid)
                applied.append({"op": op, "effect": f"added {lid} ({L['name']}, {cls}, {route}) at {L['anchors']['enter']}-{L['anchors']['exit']}"})
                continue
            L = find_layer(plan, op["layer"])
            lid = L["id"]
            if name in ("set_entry", "set_exit"):
                key = "enter" if name == "set_entry" else "exit"
                pos = _pos(op); clk.validate_position(pos["bar"], pos["beat"]); clk.t(pos["bar"], pos["beat"])
                old = L["anchors"][key]; L["anchors"][key] = pos; own(L, "anchors"); changed_ids.add(lid); rerender.add(lid)
                applied.append({"op": op, "effect": f"{lid} {key} {old['bar']}:{old['beat']:g} -> {pos['bar']}:{pos['beat']:g}"})
            elif name in ("shift_entry", "shift_exit"):
                key = "enter" if name == "shift_entry" else "exit"
                old = L["anchors"][key]
                o = clk._ordinal(old["bar"], old["beat"]) + float(op.get("by_bars", 0)) * clk.bpb + float(op.get("by_beats", 0))
                bar, beat = clk._position(o); clk.t(bar, beat)
                L["anchors"][key] = {"bar": bar, "beat": beat}; own(L, "anchors"); changed_ids.add(lid); rerender.add(lid)
                applied.append({"op": op, "effect": f"{lid} {key} {old['bar']}:{old['beat']:g} -> {bar}:{beat:g}"})
            elif name == "set_context":
                ctx = list(op.get("audio_context", []))
                earlier = ["piano"] + plan["order"][:plan["order"].index(lid)]
                bad = [c for c in ctx if c not in earlier]
                if bad:
                    raise PlanError(f"{lid} can only hear the piano or layers before it in order ({earlier}); not {bad}")
                be = (L.get("job") or {}).get("backend")
                if ctx and be in BACKENDS and "audio_context" not in BACKENDS[be]["consumes"]:
                    raise PlanError(f"{be} does not listen to audio; {lid} cannot be given an audio context")
                old = L["conditions"].get("audio_context", [])
                L["conditions"]["audio_context"] = ctx
                L["conditions"]["depends_on"] = sorted(set(ctx) | {"clock"} | ({"melody"} if L["conditions"].get("score_condition") else set()))
                own(L, "conditions"); changed_ids.add(lid); rerender.add(lid)
                applied.append({"op": op, "effect": f"{lid} audio_context {old} -> {ctx}"})
            elif name == "choose_candidate":
                cands = [c["id"] for c in L.get("candidates", [])]
                want = op.get("candidate")
                if isinstance(want, int) or (isinstance(want, str) and want.isdigit()):
                    i = int(want) - 1
                    if not 0 <= i < len(cands):
                        raise PlanError(f"{lid} has {len(cands)} candidate(s); there is no number {want}")
                    want = cands[i]
                if want not in cands:
                    raise PlanError(f"{lid} has no candidate {want!r}; candidates are {cands}")
                old = L.get("chosen"); L["chosen"] = want; own(L, "chosen")
                if old != want:
                    changed_ids.add(lid)          # descendants heard the old candidate; this layer itself is fine
                applied.append({"op": op, "effect": f"{lid} chosen {old} -> {want}"})
            elif name == "set_gain":
                old = L.get("gain_db", 0.0); L["gain_db"] = float(op["db"]); own(L, "gain")
                applied.append({"op": op, "effect": f"{lid} gain {old} -> {L['gain_db']} dB (mix-level; no re-render)"})
            elif name == "replace_with_take":
                asset = op["asset"]
                if catalog is not None and asset not in [a["id"] for a in catalog.get("assets", [])]:
                    raise PlanError(f"asset {asset!r} is not in the catalogue ({[a['id'] for a in catalog.get('assets', [])]})")
                L["kind"], L["route"], L["asset"] = "take", "take", asset
                L["job"] = {"backend": "take", "inputs": {"asset": asset}}
                L["conditions"] = {"depends_on": ["clock"], "audio_context": [], "score_condition": None, "voice_reference": None}
                L.pop("stub_reason", None); L["candidates"] = []; L["chosen"] = None; L["status"] = "planned"
                for f in ("route", "conditions", "chosen"):
                    own(L, f)
                changed_ids.add(lid)
                applied.append({"op": op, "effect": f"{lid} now the creator's take {asset}; generation job removed"})
            elif name == "set_stub":
                if L["kind"] == "stub":
                    applied.append({"op": op, "effect": f"{lid} was already a stub"}); continue
                L["before_stub"] = {"kind": L["kind"], "route": L["route"], "job": L.get("job")}
                L["kind"], L["route"], L["stub_reason"] = "stub", "stub", op.get("reason") or "set by the creator"
                L["status"] = "planned"; own(L, "route"); changed_ids.add(lid)
                applied.append({"op": op, "effect": f"{lid} is a silent placeholder now ({L['stub_reason']}); its job is kept for unstub"})
            elif name == "unstub":
                if L["kind"] != "stub":
                    applied.append({"op": op, "effect": f"{lid} is not a stub"}); continue
                prev = L.pop("before_stub", None)
                if not prev:
                    raise PlanError(f"{lid} has no remembered job to restore; add the layer again instead")
                L["kind"], L["route"], L["job"] = prev["kind"], prev["route"], prev["job"]
                L.pop("stub_reason", None); own(L, "route"); changed_ids.add(lid)
                applied.append({"op": op, "effect": f"{lid} restored to {prev['route']} ({(prev['job'] or {}).get('backend')})"})
            elif name == "set_class":
                cls = op["class"]
                if cls not in CLASSES:
                    raise PlanError(f"class {cls!r} is not one of {CLASSES}")
                if L["kind"] != "generated":
                    raise PlanError(f"{lid} is a {L['kind']}; change a take or stub by replacing it, not by renaming its class")
                old = L["class"]; L["class"] = cls
                if op.get("text"):
                    L["text"] = op["text"]
                if op.get("name"):
                    L["name"] = op["name"]
                elif L["name"] == old or L["name"] in ("pad", "synth") and cls != "synth":
                    L["name"] = cls
                L["job"]["params"]["prompt"] = build_prompt(L, analysis)
                L["job"]["params"]["track_name"] = cls
                own(L, "prompt"); changed_ids.add(lid); rerender.add(lid)
                applied.append({"op": op, "effect": f"{lid} class {old} -> {cls}; prompt rewritten"})
            elif name == "lock":
                fields = op.get("fields") or list(OWNED_FIELDS)
                for f in fields:
                    if f not in OWNED_FIELDS:
                        raise PlanError(f"cannot lock {f!r}; fields are {OWNED_FIELDS}")
                    L.setdefault("owner", {})[f] = "creator"
                applied.append({"op": op, "effect": f"{lid} fields {fields} are now the creator's; later rebuilds must preserve them"})
        except (PlanError, ClockError, KeyError, ValueError, TypeError) as e:
            refused.append({"op": op, "why": str(e)})

    if map_changed:
        # only layers whose rendered interval overlaps the re-spaced beats are stale; their descendants follow through mark_stale
        for lid in plan["order"]:
            L = layer_by_id(plan, lid)
            if L.get("candidates") and L.get("t0") is not None and any(L["t0"] < b and a < L["t1"] for a, b in clock_spans):
                rerender.add(lid); changed_ids.add(lid)
    stale = mark_stale(plan, changed_ids, reason or "revision", self_ids=rerender)
    for lid in stale:
        L = layer_by_id(plan, lid)
        if map_changed and lid in rerender and not (L.get("stale_reason") or "").startswith("the tempo map"):
            L["stale_reason"] = f"the tempo map changed inside this layer's bars after it was rendered ({reason})" if reason else "the tempo map changed inside this layer's bars after it was rendered"
    for lid in plan["order"]:
        L = layer_by_id(plan, lid)
        L["status"] = "stale" if (L.get("stale") and L.get("candidates")) else ("chosen" if L.get("chosen") else ("rendered" if L.get("candidates") else "planned"))
    problems = derive_times(plan, analysis)
    if applied and any(a["effect"] for a in applied):
        plan["revision"] = int(plan.get("revision", 0)) + 1
    for q in unresolved:
        plan.setdefault("open", {}).setdefault("questions", []).append(q)
    d = diff(before, plan)
    if map_changed:
        d.append({"path": "piano-analysis.json#tempo_map", "before": f"revision {analysis['tempo_map']['revision'] - 1}", "after": f"revision {analysis['tempo_map']['revision']}: {analysis['tempo_map']['corrections'][-1]}"})
    plan.setdefault("history", []).append({"revision": plan.get("revision", 0), "actor": actor, "reason": reason,
                                           "ops": ops, "applied": [a["effect"] for a in applied],
                                           "refused": refused, "unresolved": unresolved, "stale": stale,
                                           "paths": [c["path"] for c in d]})
    report = {"applied": applied, "refused": refused, "unresolved": unresolved, "stale": stale, "diff": d, "problems": problems}
    return plan, analysis, report


# ---- construction ----------------------------------------------------------------
def build_prompt(L, analysis):
    key = analysis.get("key") or {}
    tm = analysis.get("tempo_map") or {}
    vibe = (analysis.get("vibe") or "")
    parts = [L.get("text") or L["name"], L["class"]]
    if key.get("tonic"):
        parts.append(f"key {key['tonic']} {key.get('mode', '')}".strip())
    if tm.get("bpm_mean"):
        parts.append(f"around {tm['bpm_mean']:.0f} BPM")
    if vibe:
        parts.append(vibe)
    if L["class"] not in ("vocals", "backing vocals"):
        parts.append("no added vocals")
    return ", ".join(p for p in parts if p)


def new_layer(lid, name, cls, text, enter, exit_, route, *, from_=None, analysis=None, decision="claude"):
    L = {"id": lid, "name": name, "class": cls, "kind": "generated" if route in ("audio", "score") else route,
         "text": text, "from": from_ or {}, "anchors": {"enter": enter, "exit": exit_}, "t0": None, "t1": None,
         "route": route, "job": None, "conditions": {"depends_on": ["clock"], "audio_context": [], "score_condition": None, "voice_reference": None},
         "candidates": [], "chosen": None, "gain_db": 0.0,
         "owner": {f: ("creator" if decision == "creator" and f in ("exists", "anchors", "prompt") else "claude") for f in OWNED_FIELDS},
         "status": "planned", "stale": False, "stale_reason": None, "notes": ""}
    if route == "score":
        L["job"] = {"backend": "soulx-singer", "inputs": {"score": f"jobs/{lid}/vocal.abc", "lyrics": f"jobs/{lid}/lyrics.txt"},
                    "params": {"variants": 2, "transpose": 0}}
        L["conditions"]["score_condition"] = "melody"; L["conditions"]["voice_reference"] = "soulx:english"
        L["conditions"]["depends_on"] = ["clock", "melody"]
    elif route == "audio":
        L["job"] = {"backend": "ace-step/lego", "inputs": {"context_mix": f"jobs/{lid}/context.wav"},
                    "params": {"track_name": cls, "prompt": build_prompt(L, analysis or {}), "variants": 3, "guidance": 7.0, "steps": 50, "seed": None}}
    elif route == "stub":
        L["kind"] = "stub"
    elif route == "take":
        L["kind"] = "take"
    return L


def overlaps(a, b):
    """Half-open bar:beat intervals overlap?"""
    key = lambda p: (p["bar"], float(p["beat"]))
    return key(a["anchors"]["enter"]) < key(b["anchors"]["exit"]) and key(b["anchors"]["enter"]) < key(a["anchors"]["exit"])


def default_conditions(plan, L):
    """Vocals hear nothing (score route); sustained layers hear piano + earlier vocals that overlap them in
    time; rhythmic layers hear everything earlier that overlaps. Stubs are never heard."""
    earlier = plan["order"][:plan["order"].index(L["id"])]
    if L["route"] != "audio":
        return
    live = [x for x in earlier if layer_by_id(plan, x)["kind"] != "stub" and overlaps(L, layer_by_id(plan, x))]
    vocals = [x for x in live if layer_by_id(plan, x)["class"] in ("vocals", "backing vocals")]
    if L["class"] in RHYTHMIC:
        ctx = ["piano"] + live
    else:
        ctx = ["piano"] + vocals
    L["conditions"]["audio_context"] = ctx
    L["conditions"]["depends_on"] = sorted(set(ctx) | {"clock"})
