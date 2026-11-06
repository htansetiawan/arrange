#!/usr/bin/env python3
"""tracks.py — the creator's page: one lane per layer on the recording's own bar grid.

    python3 tracks.py arrangement.json piano-analysis.json ARRANGE-TRACKS.html [--audio piano.mp3]

Self-contained HTML, no libraries. Shows the piece, key, tempo and rubato; a
bar ruler from the measured map; a lane per layer in render order with its
route, where it enters and exits (bars, with seconds underneath), what it
hears, who decided each field, its candidates and which is chosen, and
whether it is stale; the prompt each job will be given; open questions and
unresolved facts; and the revision history. Works at phone width (the lanes
scroll sideways). Corrections are typed into the box at the bottom and
handed to revise.py; this page does not edit the plan itself.
"""
import argparse, html, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrangement as A  # noqa: E402
from clock import Clock  # noqa: E402

CSS = """
:root{--bg:#fbfaf7;--ink:#1d1c1a;--mute:#6b665e;--line:#e4e0d8;--audio:#2f6f9f;--score:#9b4f96;--take:#2e7d32;--stub:#9a9a9a;--stale:#c0392b;--accent:#b8860b}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31;--audio:#6aa6d6;--score:#c98cc4;--take:#6fbf73;--stub:#777;--stale:#ef6b5e;--accent:#e0b64a}}
:root[data-theme=dark]{--bg:#17171a;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:24px 0 8px}.mute{color:var(--mute)}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px}.grid{position:relative;min-width:720px}
.ruler{position:relative;height:28px;border-bottom:1px solid var(--line)}.bar{position:absolute;top:0;height:100%;border-left:1px solid var(--line);font-size:11px;padding-left:3px;color:var(--mute)}
.lane{position:relative;height:46px;border-bottom:1px solid var(--line)}.lane .name{position:sticky;left:0;z-index:2;display:inline-block;padding:4px 8px;font-weight:600;background:var(--bg)}
.clip{position:absolute;top:8px;height:30px;border-radius:5px;color:#fff;font-size:12px;padding:6px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.audio{background:var(--audio)}.score{background:var(--score)}.take{background:var(--take)}.stub{background:var(--stub);border:1px dashed #fff}
.stale{outline:3px solid var(--stale)}.sec{position:absolute;top:0;height:100%;border-left:2px solid var(--accent);font-size:11px;padding-left:4px;color:var(--accent)}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.tag{display:inline-block;padding:1px 6px;border-radius:4px;font-size:12px;border:1px solid var(--line);margin-right:4px}.creator{border-color:var(--take);color:var(--take)}
.warn{color:var(--stale)}code{font-size:13px}textarea{width:100%;min-height:70px;font:inherit;padding:8px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--ink)}
"""


def page(plan, analysis, audio=None):
    clk = Clock(analysis)
    tm = analysis["tempo_map"]; key = analysis.get("key", {})
    dur = float(analysis.get("source", {}).get("dur_s") or clk.end()[0])
    px_per_s = max(4.0, 1400 / dur)
    W = int(dur * px_per_s) + 40
    downbeats = [b for b in clk.beats if b["beat"] == 1]
    ruler = "".join(f'<div class="bar" style="left:{b["t"]*px_per_s:.1f}px">{b["bar"]}</div>' for b in downbeats if (b["bar"] % (1 if len(downbeats) < 60 else 4) == 0))
    secs = "".join(f'<div class="sec" style="left:{s["t0"]*px_per_s:.1f}px">{html.escape(s["label"])}</div>' for s in plan.get("sections", []))
    lanes = []
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid)
        cls = L["route"] + (" stale" if L.get("stale") else "")
        label = f'{L["name"]} · {L["route"]}' + (f' · {L["stub_reason"]}' if L["kind"] == "stub" else "") + (" · STALE" if L.get("stale") else "")
        lanes.append(f'<div class="lane"><span class="name">{L["id"]} {html.escape(L["name"])}</span>'
                     f'<div class="clip {cls}" style="left:{L["t0"]*px_per_s:.1f}px;width:{max(8,(L["t1"]-L["t0"])*px_per_s):.1f}px" title="{html.escape(L.get("text") or "")}">{html.escape(label)}</div></div>')
    rows = []
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid); a = L["anchors"]; c = L.get("conditions") or {}
        own = L.get("owner") or {}
        tags = "".join(f'<span class="tag creator">{f}: creator</span>' for f, v in own.items() if v == "creator")
        hears = ", ".join(c.get("audio_context") or []) or ("melody (score)" if c.get("score_condition") else "nothing")
        cands = L.get("candidates") or []
        cand = (f'{len(cands)} candidate(s), chosen: {L.get("chosen") or "none yet"}') if cands else "not rendered yet"
        prompt = (L.get("job") or {}).get("params", {}).get("prompt") or ("sung from the melody with the lyrics" if L["route"] == "score" else L.get("stub_reason") or "the creator's take")
        stale = f'<div class="warn">stale: {html.escape(L.get("stale_reason") or "")}</div>' if L.get("stale") else ""
        rows.append(f'<tr><td><b>{L["id"]}</b> {html.escape(L["name"])}<br><span class="mute">{L["class"] or "?"} · {L["route"]}</span></td>'
                    f'<td>bar {a["enter"]["bar"]}:{a["enter"]["beat"]:g} → {a["exit"]["bar"]}:{a["exit"]["beat"]:g}<br><span class="mute">{L["t0"]:.2f}s – {L["t1"]:.2f}s</span></td>'
                    f'<td>{html.escape(hears)}</td><td>{html.escape(prompt)}{stale}</td><td>{cand}<br>{tags}</td></tr>')
    qs = "".join(f"<li>{html.escape(q)}</li>" for q in plan.get("open", {}).get("questions", [])) or "<li class=mute>none</li>"
    us = "".join(f"<li>{html.escape(q)}</li>" for q in plan.get("open", {}).get("unresolved_specs", [])) or "<li class=mute>none</li>"
    hist = "".join(f'<li><b>rev {h.get("revision")}</b> ({h.get("actor")}): {html.escape(h.get("reason") or "")}<br>'
                   + "".join(f'<span class="mute">· {html.escape(e)}</span><br>' for e in h.get("applied", []))
                   + "".join(f'<span class="warn">· refused: {html.escape(r["why"])}</span><br>' for r in h.get("refused", []))
                   + (f'<span class="warn">· stale: {", ".join(h["stale"])}</span>' if h.get("stale") else "") + "</li>"
                   for h in plan.get("history", [])) or "<li class=mute>no revisions yet</li>"
    audio_el = f'<p><audio controls src="{html.escape(audio)}" style="width:100%"></audio></p>' if audio else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(plan.get("piece") or "Arrangement")} tracks</title><style>{CSS}</style></head><body>
<h1>{html.escape(plan.get("piece") or "Arrangement")}</h1>
<p class="mute">{html.escape(key.get("tonic", "?"))} {html.escape(key.get("mode", ""))} · {tm.get("time_signature", "4/4")} · about {tm.get("bpm_mean", 0):.0f} BPM, rubato {tm.get("rubato", "?")} · map: {html.escape(str(tm.get("method")))} (revision {tm.get("revision", 0)}) · plan revision {plan.get("revision", 0)}</p>
{audio_el}
<div class="wrap"><div class="grid" style="width:{W}px"><div class="ruler">{ruler}{secs}</div>{"".join(lanes)}</div></div>
<p class="mute">Blue = generated from audio (ACE-Step), purple = sung from a score (SoulX), green = your own take, grey dashed = silent placeholder. A red outline means the layer must be re-rendered because something it depended on changed.</p>
<h2>Layers</h2><table><tr><th>Layer</th><th>Where</th><th>Hears</th><th>What the job is asked for</th><th>Candidates · decided by you</th></tr>{"".join(rows)}</table>
<h2>Open questions</h2><ul>{qs}</ul>
<h2>Facts still uncertain in the analysis</h2><ul>{us}</ul>
<h2>Revisions</h2><ol>{hist}</ol>
<h2>Tell me what to change</h2><p class="mute">Write it the way you would say it to a player: “strings two bars later”, “use the second vocal”, “keep my guitar exactly”, “bar 17 starts a beat late”. The words become typed operations you can read before they are applied.</p>
<textarea placeholder="e.g. bring the strings in two bars later and let them hear the piano only"></textarea>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arrangement"); ap.add_argument("analysis"); ap.add_argument("out"); ap.add_argument("--audio")
    a = ap.parse_args()
    Path(a.out).write_text(page(A.load(a.arrangement), A.load(a.analysis), a.audio), encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
