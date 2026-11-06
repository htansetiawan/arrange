#!/usr/bin/env python3
"""canvas.py — the score as a canvas: one hosted page, updated in place each iteration (/arrange-lyrics; analysis python).

    python canvas.py --score jobs/verse1/score.json --analysis piano-analysis.json --mix mix.mp3 [--reference ref.mp3] [--chords melody.json]
                     --title "..." -o jobs/verse1/canvas/ [--artifact] [--history "..."]

The engraved line with the words under the notes (in blue: they are
clickable) and a number under each note within its line, bar numbers in the
composer's count, the key's accidentals only; chord symbols only when
--chords is given. Click a note to hear the piano and the voice from there;
voice pills switch between sung mixes, a checkbox turns the voice off, and the
reference singer can be switched in. Below: the lines (start time, notated
bar, words) and, with --sung, the sounds sent to the singer for each
syllable. The chat is the pen; this page only shows.
"""
import argparse, base64, html, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
import notate  # noqa: E402
from feel import feel  # noqa: E402

COLORS = {"composer": "#2f6f9f", "reference": "#8e44ad", "tool": "#b8860b", "piano": "#1d1c1a", "unsung": "#a3a39e"}


def provenance(r):
    if r.get("kind") == "unsung":
        return "unsung"
    pl = (r.get("placed") or "").lower()
    if "dictated" in pl or "composer" in pl:
        return "composer"
    if "reference" in pl or "transcribed" in pl or "heard" in pl:
        return "reference"
    if "split" in pl or "held" in pl or "tool" in pl or r.get("kind") == "slur":
        return "tool"
    return "piano"


def chord_names(melody_json, first_bar, last_bar):
    if not melody_json:
        return []
    d = json.load(open(melody_json)); out = []
    for bar, name in d.get("chords_by_bar", []):
        if first_bar <= bar <= last_bar:
            n = name.replace("B-", "Bb").replace("A-", "Ab").replace("E-", "Eb").replace("D-", "Db").replace("pedal", "").replace("power", "5").replace("addG", "add9")
            out.append((bar, n))
    return out


def notated_note_rows(xml_path, rows):
    """Map each notated note (document order, rests skipped) to a row index; a tie-continuation maps to the same row."""
    xml = Path(xml_path).read_text()
    notes = re.findall(r"<note[^>]*>(.*?)</note>", xml, flags=re.S)
    mapping, ri = [], -1
    for body in notes:
        if "<rest" in body:
            continue
        if re.search(r'<tie type="stop"', body) and not re.search(r'<tie type="start"', body) or (re.search(r'<tie type="stop"', body) and re.search(r'<tie type="start"', body)):
            mapping.append(ri); continue
        ri += 1; mapping.append(ri)
    return mapping


def line_words(ln):
    """The line as words: syllables of one word joined (Mor+ning -> Morning), held notes skipped."""
    out, acc, word = [], "", None
    for r in ln:
        t = r.get("text") or ""
        if r.get("kind") != "note" or not t or t == "~":
            continue
        w = "".join(ch for ch in (r.get("word") or "") if ch.isalpha()).lower()
        piece = "".join(ch for ch in t if ch.isalpha()).lower()
        if acc and w == word and w.startswith(acc_l + piece):
            acc += t; acc_l += piece
        else:
            if acc:
                out.append(acc)
            acc, acc_l, word = t, piece, w
        if acc_l == word:
            out.append(acc); acc, acc_l, word = "", "", None
    if acc:
        out.append(acc)
    return " ".join(out) or "·"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--mix", required=True); ap.add_argument("--reference")
    ap.add_argument("--mix-label", default="voice", help="name on the pill of the default mix")
    ap.add_argument("--voice", action="append", default=[], help="another sung mix as label=path; each gets a pill to switch to it")
    ap.add_argument("--chords"); ap.add_argument("--title", required=True); ap.add_argument("-o", "--out", required=True); ap.add_argument("--artifact", action="store_true")
    ap.add_argument("--audio-start", type=float, default=0.0); ap.add_argument("--history", action="append", default=[])
    ap.add_argument("--grid", type=int, default=4, help="score spelling: 4 = half-beats of the composer's beat (easier to read; the default), 8 = quarter-beats (shows every short note)")
    ap.add_argument("--sung", help="the sung score sent to the singer (build/sung-score.json): shows each syllable's sounds")
    ap.add_argument("--recorder-url", help="link to the Play the Line recorder for this piece")
    ap.add_argument("--beat-offset", type=float, default=0.0, help="move the notation this many of the composer's beats later against the bar lines (the sound is not moved)")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    an = json.load(open(a.analysis)); sc = json.load(open(a.score)); rows = list(sc["rows"]); clk = Clock(an)
    per, bpb, ts = feel(an)   # the composer's beats per map beat, the composer's beats per notated bar
    q = notate.quantise([dict(r) for r in rows], clk, a.grid)
    for r in q:   # --beat-offset counts the composer's beats; ordinals count map beats
        r["ordinal"] += a.beat_offset / per
    first_bar = int(q[0]["ordinal"] * per // bpb) + 1; last_bar = int(q[-1]["ordinal"] * per // bpb) + 2
    kinfo = json.load(open(a.analysis)).get("key") or {}
    notate.write_musicxml(q, out / "score.musicxml", a.title, a.grid, line_numbers=True, chords=chord_names(a.chords, first_bar, last_bar),
                          key_name=kinfo.get("tonic", "F"), mode=kinfo.get("mode", "major"),
                          bpm=int(round(per * (an["tempo_map"].get("bpm_mean") or 46))), per=per, ts=ts)   # the composer's beat = 1/per of a map beat
    pages = notate.engrave(out / "score.musicxml", out / "score.svg")
    mapping = notated_note_rows(out / "score.musicxml", q)
    svg_all = ""
    for pg in pages:
        svg = pg.read_text()
        # colour and time every notated note, in document order
        k = [0]
        def tag(m):
            i = k[0]; k[0] += 1
            ri = mapping[i] if i < len(mapping) else None
            if ri is None or ri >= len(q):
                return m.group(0)
            r = q[ri]; col = COLORS[provenance(r)]
            return m.group(1) + f' data-t="{r["t"]:.3f}" data-row="{ri}" style="cursor:pointer" '
        svg = re.sub(r'(<g\b[^>]*class="note"[^>]*)', lambda m: tag(m) if True else m.group(0), svg)
        svg = re.sub(r'<svg[^>]*?(width="[^"]*")', lambda m: m.group(0).replace(m.group(1), 'width="100%"'), svg, count=1)
        svg = re.sub(r'(<g [^>]*class="verse"[^>]*)>(\s*<title class="labelAttr">)(\d)(</title>)', r'\1 data-verse="\3">\2\3\4', svg)   # verse 1 = the words, 2 = note numbers
        svg_all += svg
    def src(path):
        if not path:
            return ""
        if a.artifact:
            return "data:audio/mpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()
        return html.escape(Path(path).name)
    legend = "".join(f'<span class="sw" style="background:{c}"></span>{n}&nbsp;&nbsp;' for n, c in (("from the piano's own line", COLORS["piano"]), ("played or dictated by you", COLORS["composer"]), ("from the reference singer", COLORS["reference"]), ("split or held by the tool", COLORS["tool"]), ("placed, no words yet", COLORS["unsung"])))
    history = a.history or sc.get("report", [])
    hist_html = "".join(f"<li>{html.escape(h)}</li>" for h in history) or "<li class=mute>none yet</li>"
    lines = []
    cur = []
    for i, r in enumerate(rows):
        if i and r["t"] - rows[i - 1]["end"] >= 1.0:
            lines.append(cur); cur = []
        if r["kind"] in ("note", "unsung"):
            cur.append(r)
    if cur:
        lines.append(cur)
    ph_at = {}
    if a.sung and Path(a.sung).exists():
        for r in json.load(open(a.sung))["rows"]:
            if r.get("kind") == "note" and r.get("phoneme"):
                ph_at[round(r["t"], 2)] = " ".join(re.sub(r"\d", "", x) for x in r["phoneme"].replace("en_", "").split("-"))

    def sounds(ln):
        """Each sung syllable over the sounds the singer was given for it (ARPAbet, stress marks dropped)."""
        if not ph_at:
            return ""
        chips = "".join(f'<span><b>{html.escape(r["text"])}</b><i>{html.escape(ph_at.get(round(r["t"], 2), "?"))}</i></span>'
                        for r in ln if r.get("kind") == "note" and r.get("text") and r["text"] != "~")
        return f'<div class="syl" title="what the singer is told to pronounce on each note">{chips}</div>'

    first_sung = next((r["t"] for r in rows if r.get("kind") == "note" and r.get("text")), None)
    alts = [v.split("=", 1) for v in a.voice]
    pills_html = ('<div class="pills" role="group" aria-label="voice">' + f'<button class="pill on" data-a="mix">{html.escape(a.mix_label)}</button>'
                  + "".join(f'<button class="pill" data-a="mix-{k + 1}">{html.escape(lab)}</button>' for k, (lab, _) in enumerate(alts)) + '</div>') if alts else ""
    alt_audio = "".join(f'<audio id="mix-{k + 1}" preload="none" src="{src(path)}"></audio>' for k, (_, path) in enumerate(alts))
    lines_html = "".join(f'<li><b>line {i + 1}</b> · starts {ln[0]["t"]:.1f} s · notated bar {int((clk._ordinal(*clk.at(ln[0]["t"])) + a.beat_offset / per) * per // bpb) + 1} · {line_words(ln)}{sounds(ln)}</li>' for i, ln in enumerate(lines))
    head = (f"<title>{html.escape(a.title)}</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n" if a.artifact else f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(a.title)}</title>\n')
    page = head + f"""<style>
:root{{--bg:#ffffff;--ink:#191919;--mute:#787774;--line:#e9e9e7;--panel:#f7f7f5;--acc:#191919}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#ffffff;--ink:#191919;--mute:#787774;--line:#e9e9e7;--panel:#f7f7f5;color-scheme:light}}}}
:root[data-theme=dark]{{--bg:#ffffff;--ink:#191919;--mute:#787774;--line:#e9e9e7;--panel:#f7f7f5;color-scheme:light}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
#app{{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:12px;max-width:1400px;margin:0 auto}}
h1{{font-size:30px;font-weight:700;letter-spacing:-.01em;margin:18px 0 6px}}h2{{font-size:15px;margin:18px 0 6px}}.mute{{color:var(--mute)}}a{{color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}}a:hover{{text-decoration-color:var(--ink)}}
.bar{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}}button{{padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink);cursor:pointer;font:inherit}}button:hover{{background:var(--panel)}}.ib{{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;padding:0}}.ib svg{{width:18px;height:18px;fill:currentColor}}
.score g.verse[data-verse="1"] text{{fill:#5a8fd6}}.score g.verse[data-verse="2"] text{{fill:#9b9a97}}.score g.note[data-t]:hover g.verse[data-verse="1"] text{{fill:#2f6fc4}}
.startcue{{position:absolute;display:flex;align-items:center;gap:8px;transform:translateX(-17px)}}.startcue button{{width:34px;height:34px;border-radius:50%;border:0;padding:0;background:#2f6fc4;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.18)}}.startcue button:hover{{background:#1f4f94}}.startcue button svg{{width:14px;height:14px;fill:#fff;margin-left:2px}}.startcue .lbl{{font:600 12.5px/1.2 ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#2f6fc4;white-space:nowrap;cursor:pointer}}.startline{{position:absolute;width:0;border-left:1.5px dashed #2f6fc4;opacity:.6;pointer-events:none}}
.score{{position:relative;background:#fff;border:0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:52px 0 12px;overflow-x:auto}}.score svg{{max-width:100%;height:auto}}
.sw{{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 4px -1px 0}}.chk{{display:inline-flex;gap:4px;align-items:center}}
ol,ul{{padding-left:20px}}li{{margin:3px 0}}code{{background:var(--panel);padding:1px 4px;border-radius:3px}}
.syl{{display:flex;flex-wrap:wrap;gap:4px;margin:5px 0 10px}}.syl span{{display:inline-flex;flex-direction:column;align-items:center;border:1px solid var(--line);border-radius:5px;padding:2px 6px;font-size:13px;line-height:1.3}}.syl i{{font-style:normal;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--mute)}}
.pills{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}}.pill{{border:1px solid var(--line);border-radius:999px;padding:5px 13px;background:#fff;color:var(--ink);cursor:pointer;font:inherit;font-size:13px}}.pill.on{{background:var(--acc);border-color:var(--acc);color:#fff}}
.cols{{display:block;max-width:900px}}@media (max-width:860px){{.cols{{grid-template-columns:1fr}}}}
</style>{'' if a.artifact else '</head><body>'}
<div id="app"><h1>{html.escape(a.title)}</h1>
<p class="mute">Click any note to hear the piano and the voice from there.{f' <a href="{html.escape(a.recorder_url)}">Play the Line</a> to play a new take over the recording.' if a.recorder_url else ''}</p>
<div class="bar"><button class="ib" onclick="seekRel(-5)" title="Back 5 seconds" aria-label="Back 5 seconds"><svg viewBox="0 0 24 24"><path d="M11 6v12l-8.5-6zM21 6v12l-8.5-6z"/></svg></button><button class="ib" id="playBtn" onclick="toggle()" title="Play" aria-label="Play"><svg viewBox="0 0 24 24"><path d="M7 5v14l12-7z"/></svg></button><button class="ib" onclick="seekRel(5)" title="Forward 5 seconds" aria-label="Forward 5 seconds"><svg viewBox="0 0 24 24"><path d="M13 6v12l8.5-6zM3 6v12l8.5-6z"/></svg></button>
<label class="chk"><input type="checkbox" id="voiceOn" checked> voice</label>{'<label class="chk"><input type="checkbox" id="refOn"> reference singer instead</label>' if a.reference else ''}<span id="clock" class="mute">0.0 s</span></div>
{pills_html}<audio id="mix" preload="auto" src="{src(a.mix)}"></audio>{alt_audio}{f'<audio id="ref" preload="auto" src="{src(a.reference)}"></audio>' if a.reference else ''}
<div class="score" id="score">{svg_all}</div>
<div class="cols"><div><h2>Lines</h2><ol>{lines_html}</ol>
</div></div></div>
<script>
let mix = document.getElementById('mix'); const ref = document.getElementById('ref');
document.querySelectorAll('.pill').forEach(b => b.addEventListener('click', () => {{   // switch voice, same place in the song
  const next = document.getElementById(b.dataset.a); if (!next || next === mix) return;
  const t = mix.currentTime, playing = !mix.paused; mix.pause(); mix = next;
  const go = () => {{ mix.currentTime = t; if (playing) mix.play(); }}; if (mix.readyState >= 1) go(); else {{ mix.addEventListener('loadedmetadata', go, {{once: true}}); mix.load(); }}
  document.querySelectorAll('.pill').forEach(x => x.classList.toggle('on', x === b)); }})); const START = {a.audio_start};
function setIcon(p){{ const b = document.getElementById('playBtn'); b.innerHTML = p ? '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>' : '<svg viewBox="0 0 24 24"><path d="M7 5v14l12-7z"/></svg>'; b.title = b.ariaLabel = p ? 'Pause' : 'Play'; }}
function cur(){{ return (document.getElementById('refOn') && document.getElementById('refOn').checked && ref) ? ref : mix; }}
function other(){{ return cur() === mix ? ref : mix; }}
function play(t){{ const c = cur(); if (other()) other().pause(); c.currentTime = Math.max(0, t - START); c.play(); setIcon(true); }}
function pause(){{ mix.pause(); if (ref) ref.pause(); setIcon(false); }}
function toggle(){{ const c = cur(); if (c.paused) play(c.currentTime + START); else pause(); }}
const FIRST = {first_sung if first_sung is not None else 'null'};
function placeCue(){{   // a round play button above the score, a dashed line down to the first sung note, a label beside it
  if (FIRST === null) return; const sc = document.getElementById('score');
  const g = [...sc.querySelectorAll('g.note[data-t]')].find(x => Math.abs(parseFloat(x.dataset.t) - FIRST) < 0.02); if (!g) return;
  let cue = document.getElementById('startcue'), line = document.getElementById('startline');
  if (!cue) {{ cue = document.createElement('div'); cue.id = 'startcue'; cue.className = 'startcue';
    cue.innerHTML = '<button type="button" aria-label="Play from where the words start" title="Play from where the words start"><svg viewBox="0 0 24 24"><path d="M7 5v14l12-7z"/></svg></button><span class="lbl">Play from the words</span>';
    cue.addEventListener('click', e => {{ play(FIRST - 2); e.stopPropagation(); }}); sc.appendChild(cue);
    line = document.createElement('div'); line.id = 'startline'; line.className = 'startline'; sc.appendChild(line); }}
  const r = g.getBoundingClientRect(), s0 = sc.getBoundingClientRect(), x = r.left - s0.left + sc.scrollLeft + r.width / 2, noteTop = r.top - s0.top + sc.scrollTop;
  cue.style.left = x + 'px'; cue.style.top = '6px';
  line.style.left = x + 'px'; line.style.top = '42px'; line.style.height = Math.max(0, noteTop - 48) + 'px'; }}
window.addEventListener('load', placeCue); window.addEventListener('resize', placeCue); setTimeout(placeCue, 300);
if (FIRST !== null && FIRST > START + 6) {{   // the play button starts two seconds before the words
  const cueStart = () => {{ if (mix.currentTime < 0.05) mix.currentTime = Math.max(0, FIRST - 2 - START); }};
  if (mix.readyState >= 1) cueStart(); else mix.addEventListener('loadedmetadata', cueStart, {{once: true}}); }}
function seekRel(d){{ const c = cur(); c.currentTime = Math.max(0, c.currentTime + d); }}
document.querySelectorAll('g.note[data-t]').forEach(g => g.addEventListener('click', e => {{ play(parseFloat(g.dataset.t) - 0.3); e.stopPropagation(); }}));
document.addEventListener('change', e => {{ if (e.target.id === 'voiceOn') mix.muted = false; }});
setInterval(() => {{ const c = cur(); document.getElementById('clock').textContent = (c.currentTime + START).toFixed(1) + ' s'; document.querySelectorAll('g.note[data-t]').forEach(g => {{ const t = parseFloat(g.dataset.t); g.style.opacity = (c.currentTime + START >= t && c.currentTime + START < t + 1.2) ? '0.55' : '1'; }}); }}, 120);
</script>{'' if a.artifact else '</body></html>'}"""
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {out / 'index.html'}: {len(q)} notes, {len(lines)} lines, {len(pages)} page(s), {sum(1 for m in mapping if m is not None)} clickable notes")


if __name__ == "__main__":
    main()
