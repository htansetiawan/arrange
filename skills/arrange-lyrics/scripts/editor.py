#!/usr/bin/env python3
"""editor.py — the composer's page for putting words on notes (/arrange-lyrics).

    python editor.py --fit lyric-fit.json --audio piano-excerpt.mp3 --audio-start 68 [--voice voice-mix.mp3] [--title "..."] -o lyric-editor/index.html

Self-contained HTML, no libraries. The melody is drawn on a timeline (pitch
up, time across, bar numbers below) with the syllable on every note and a
playhead that follows the piano and, if given, the current voice. The composer
clicks or arrows to a note, types the syllable in place, holds the previous
one (~), leaves a note unsung, splits a note into two halves at the same
pitch, merges it with the next, nudges the pitch, and shifts the words along a
phrase. One line box per phrase shows syllables against notes. Warnings name
every syllable that sits on a note too short to sing. Undo and redo. Save
downloads lyric-fit.edited.json, which fit.py --edits applies exactly as
written. The composer owns every placement; the page only shows and records.
"""
import argparse, html, json
from pathlib import Path

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", required=True); ap.add_argument("--audio", required=True); ap.add_argument("--audio-start", type=float, default=0.0)
    ap.add_argument("--voice"); ap.add_argument("--reference", help="a sung reference (e.g. the composer's Suno version's voice stem) on the same clock, as a third track")
    ap.add_argument("--title", default="Words on notes"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--phrase-gap-s", type=float, default=3.0); ap.add_argument("--short-s", type=float, default=0.15)
    ap.add_argument("--inline-audio", action="store_true", help="embed the audio files in the page (one self-contained file to send to a phone or another machine)")
    ap.add_argument("--artifact", action="store_true", help="hosted mode for a claude.ai artifact: no document skeleton, Save writes to the page's own store (db capability), Copy as fallback")
    ap.add_argument("--store-doc", default="fits/theme2", help="artifact mode: the store document that holds the current fit")
    a = ap.parse_args()
    import base64, mimetypes

    def src_of(path):
        if not a.inline_audio:
            return html.escape(Path(path).name)
        mime = mimetypes.guess_type(path)[0] or "audio/mpeg"
        return f"data:{mime};base64," + base64.b64encode(Path(path).read_bytes()).decode()
    sc = json.load(open(a.fit)); rows = sorted(sc["rows"], key=lambda r: r["t"])
    data = {"title": a.title, "rows": [{"t": r["t"], "end": r["end"], "pitch": r["pitch"], "bar": r.get("bar"), "beat": r.get("beat"), "text": r.get("text", ""),
                                        "kind": r.get("kind", "note"), "word": r.get("word"), "placed": r.get("placed", "performance")} for r in rows],
            "lines": sc.get("lines", []), "audio_start": a.audio_start, "phrase_gap": a.phrase_gap_s, "short": a.short_s, "source": str(a.fit), "has_voice": bool(a.voice),
            "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"), "store_doc": a.store_doc, "artifact": a.artifact}
    voice_el = (f'<audio id="voice" preload="auto" src="{src_of(a.voice)}"></audio>' if a.voice else "") + (f'<audio id="ref" preload="auto" src="{src_of(a.reference)}"></audio>' if a.reference else "")
    voice_btn = ('<label class="chk"><input type="checkbox" id="voiceOn" checked> voice</label>' if a.voice else "") + ('<label class="chk"><input type="checkbox" id="refOn"> reference singer</label>' if a.reference else "")
    head = ('<title>__TITLE__</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n' if a.artifact else '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n<title>__TITLE__</title>\n')
    head += '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
    tail_open = '' if a.artifact else '</head><body>'
    page = head + r"""<style>
:root{--bg:#fbfaf7;--ink:#1d1c1a;--mute:#6f6a62;--line:#e2ddd4;--panel:#f3f0ea;--note:#2f6f9f;--hold:#b8860b;--off:#a3a39e;--sel:#d7263d;--warn:#c0392b;--ok:#2e7d32;--play:#111}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141417;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31;--panel:#1d1d22;--note:#6aa6d6;--hold:#e0b64a;--off:#5c5c60;--sel:#ff6b6b;--warn:#ef6b5e;--ok:#6fbf73;--play:#fff;color-scheme:dark}}
:root[data-theme=dark]{--bg:#141417;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31;--panel:#1d1d22;--note:#6aa6d6;--hold:#e0b64a;--off:#5c5c60;--sel:#ff6b6b;--warn:#ef6b5e;--ok:#6fbf73;--play:#fff;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;min-height:100%;background:var(--bg);color:var(--ink);font:14px/1.4 "IBM Plex Sans",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;display:flex;flex-direction:column;font-variant-numeric:tabular-nums}
#app{display:flex;flex-direction:column;min-height:100vh;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:0}
header{padding:10px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.banner{padding:6px 0;font-size:13px;color:var(--mute)}.banner b{color:var(--ok)}
h1{font-size:17px;margin:0 12px 0 0}.mute{color:var(--mute)}button{padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);cursor:pointer;font:inherit}
button.primary{background:var(--note);color:#fff;border-color:var(--note)}button:disabled{opacity:.4}.chk{display:inline-flex;gap:4px;align-items:center;font-size:13px}.scrub{display:inline-flex;gap:8px;align-items:center;flex:1 1 220px;min-width:160px}.scrub input{flex:1;min-width:120px;accent-color:var(--note)}#clock{font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace;font-size:12px;min-width:92px}
#wrap{flex:1;overflow:auto;position:relative;border-bottom:1px solid var(--line)}#timeline{position:relative;height:420px}
.ruler{position:absolute;left:0;right:0;top:0;height:22px;border-bottom:1px solid var(--line);font-size:11px;color:var(--mute);cursor:pointer}#timeline{cursor:crosshair}.note{cursor:pointer}
.ruler .tick{position:absolute;top:0;height:100%;border-left:1px solid var(--line);padding-left:3px;font-family:"IBM Plex Mono",ui-monospace,Menlo,monospace}.ruler .bar{border-left:2px solid var(--mute);font-weight:600;color:var(--ink)}
.phr{position:absolute;top:22px;bottom:0;border-left:1px dashed var(--line)}.phr span{position:absolute;top:2px;left:4px;font-size:11px;color:var(--mute);white-space:nowrap}
.note{position:absolute;height:22px;border-radius:4px;background:var(--note);color:#fff;font-size:12px;line-height:22px;padding:0 5px;white-space:nowrap;overflow:visible;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,.25)}
.note.hold{background:var(--hold)}.note.unsung{background:var(--off);color:#fff}.note.sel{outline:3px solid var(--sel);z-index:3}.note.warn::after{content:"!";position:absolute;right:-6px;top:-9px;color:var(--warn);font-weight:700;font-size:14px}
.note .lab{position:absolute;left:0;top:24px;color:var(--ink);font-size:12px;font-weight:600;white-space:nowrap}.note.narrow .lab{display:none}.note.narrow.sel .lab,.note.narrow:hover .lab{display:block;z-index:5;background:var(--bg);padding:0 3px;border-radius:3px}.note.narrow>span:first-child{display:block;overflow:hidden;text-overflow:ellipsis}
#playhead{position:absolute;top:0;bottom:0;width:2px;background:var(--play);z-index:4;pointer-events:none}
#panels{display:grid;grid-template-columns:1fr 1fr;gap:0}@media (max-width:860px){#panels{grid-template-columns:1fr}}
.panel{padding:12px 16px 12px 0;border-right:1px solid var(--line);min-width:0}.panel+.panel{padding-left:16px;border-right:0}.panel h2{font-size:14px;margin:0 0 8px}
.insp{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.insp input{padding:6px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--ink);font:16px inherit;width:120px}
.line{display:grid;grid-template-columns:70px 1fr auto auto;gap:6px;align-items:center;margin:4px 0}.line input{padding:5px;border:1px solid var(--line);border-radius:5px;background:transparent;color:var(--ink);font:inherit}
.cnt{font-size:12px;min-width:92px}.cnt.ok{color:var(--ok)}.cnt.bad{color:var(--warn)}
#warns{font-size:13px;margin:0;padding-left:18px}#warns li{margin:2px 0}.warn{color:var(--warn)}
textarea{width:100%;min-height:48px;font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;background:transparent;color:var(--ink)}
kbd{border:1px solid var(--line);border-radius:3px;padding:0 4px;font-size:11px;background:var(--panel)}
</style>__TAILOPEN__
<div id="app"><header><h1>__TITLE__</h1>
<button onclick="seek(0)" title="to the start">⏮</button><button onclick="seekRel(-2)" title="back two seconds">−2 s</button><button id="playBtn" class="primary" onclick="toggle()">▶ play</button><button onclick="seekRel(2)" title="forward two seconds">+2 s</button><button onclick="playFrom(sel)" title="Space">▶ from note</button><button onclick="playPhrase()">▶ phrase</button>
<span class="scrub"><input type="range" id="scrub" min="0" max="50" step="0.05" value="0" oninput="seek(parseFloat(this.value))"><span id="clock" class="mute">0.0 s</span></span>
<label class="chk"><input type="checkbox" id="pianoOn" checked> piano</label>__VOICEBTN__
<span class="mute" id="status"></span><span style="flex:1"></span>
<button onclick="undo()" title="Ctrl+Z">undo</button><button onclick="redo()" title="Ctrl+Y">redo</button><button onclick="resetAll()">reset</button><button onclick="copyJson()">copy JSON</button><button class="primary" id="saveBtn" onclick="save()">__SAVELABEL__</button></header>
<div class="banner" id="banner"></div>
<audio id="piano" preload="auto" src="__AUDIO__"></audio>__VOICEEL__
<div id="wrap"><div id="timeline"><div class="ruler" id="ruler"></div><div id="playhead" style="left:0"></div></div></div>
<div id="panels">
<div class="panel"><h2>Selected note <span class="mute" id="selInfo"></span></h2>
<div class="insp"><input id="selText" placeholder="syllable" onchange="setText(sel, this.value)"><button onclick="hold(sel)" title="H">~ hold</button><button onclick="mute(sel)" title="U">· unsung</button><button onclick="split(sel)" title="S">split</button><button onclick="merge(sel)" title="M">merge</button><button onclick="nudge(sel,1)">pitch +</button><button onclick="nudge(sel,-1)">pitch −</button><button onclick="shift(sel,1)" title="Shift+→">words →</button><button onclick="shift(sel,-1)" title="Shift+←">words ←</button></div>
<p class="mute" style="font-size:12px;margin:8px 0 0">Keys: <kbd>←</kbd><kbd>→</kbd> move · <kbd>Enter</kbd> edit · <kbd>Space</kbd> play from note · <kbd>H</kbd> hold · <kbd>U</kbd> unsung · <kbd>S</kbd> split · <kbd>M</kbd> merge · <kbd>Shift+←/→</kbd> shift words · <kbd>Ctrl+Z/Y</kbd> undo/redo. Blue = sung, gold = held, grey = unsung, red ! = too short to carry its syllable.</p>
<h2 style="margin-top:14px">Warnings</h2><ul id="warns"></ul></div>
<div class="panel"><h2>Lines, one per phrase</h2><div id="lines"></div><p class="mute" style="font-size:12px">Type a line and press <b>fit</b> to lay it on that phrase (fast runs become holds). The count shows syllables against notes that can carry one.</p>
<h2 style="margin-top:14px">Note to the next render</h2><textarea id="note" placeholder="anything the voice should know about this fit"></textarea></div></div></div>
<script>
const DATA = __DATA__;
const NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
let rows = JSON.parse(JSON.stringify(DATA.rows)); let sel = 0; const undoS = [], redoS = [];
const PX = 110; const el = id => document.getElementById(id);
const nameOf = p => NAMES[p % 12] + (Math.floor(p / 12) - 1);
function kindOf(t){ t = (t || '').trim(); return t === '' ? 'unsung' : (t === '~' ? 'slur' : 'note'); }
function phrases(){ const out = []; let cur = [0]; for (let k = 1; k < rows.length; k++) { if (rows[k].t - rows[k-1].t >= DATA.phrase_gap) { out.push(cur); cur = []; } cur.push(k); } out.push(cur); return out; }
function slots(){ return rows.map((r, k) => { const dur = r.end - r.t; const gap = k === 0 || r.t - rows[k-1].end > 0.1; const nd = k + 1 < rows.length ? rows[k+1].end - rows[k+1].t : 0; const pd = k > 0 ? rows[k-1].end - rows[k-1].t : 1;
  return gap || dur >= 0.2 || (dur < 0.2 && nd >= 0.4 && pd >= 0.2); }); }
function snap(){ undoS.push(JSON.stringify({rows, sel})); if (undoS.length > 100) undoS.shift(); redoS.length = 0; }
function undo(){ if (!undoS.length) return; redoS.push(JSON.stringify({rows, sel})); ({rows, sel} = JSON.parse(undoS.pop())); render(); }
function redo(){ if (!redoS.length) return; undoS.push(JSON.stringify({rows, sel})); ({rows, sel} = JSON.parse(redoS.pop())); render(); }
function resetAll(){ snap(); rows = JSON.parse(JSON.stringify(DATA.rows)); sel = 0; render(); }
function setText(i, t){ snap(); rows[i].text = t.trim(); rows[i].kind = kindOf(t); if (rows[i].kind === 'note') rows[i].word = t.trim(); render(); }
function hold(i){ setText(i, '~'); } function mute(i){ setText(i, ''); }
function split(i){ snap(); const r = rows[i]; const mid = +(r.t + (r.end - r.t) / 2).toFixed(3); const s = JSON.parse(JSON.stringify(r)); r.end = mid; s.t = mid; s.text = '~'; s.kind = 'slur'; s.placed = 'split by the composer'; rows.splice(i + 1, 0, s); render(); }
function merge(i){ if (i + 1 >= rows.length) return; snap(); rows[i].end = rows[i+1].end; rows.splice(i + 1, 1); if (sel >= rows.length) sel = rows.length - 1; render(); }
function nudge(i, d){ snap(); rows[i].pitch += d; render(); }
function shift(i, dir){ snap(); const ph = phrases().find(p => p.includes(i)); const idx = ph.indexOf(i); const texts = ph.map(k => rows[k].text);
  if (dir > 0) { for (let j = ph.length - 1; j > idx; j--) texts[j] = texts[j-1]; texts[idx] = '~'; } else { for (let j = idx; j < ph.length - 1; j++) texts[j] = texts[j+1]; texts[ph.length-1] = '~'; }
  ph.forEach((k, j) => { rows[k].text = texts[j]; rows[k].kind = kindOf(texts[j]); if (rows[k].kind === 'note') rows[k].word = texts[j]; }); render(); }
function sylls(word){ const m = word.toLowerCase().match(/[^aeiouy]*[aeiouy]+(?:[^aeiouy]*(?=[^aeiouy]*[aeiouy])|[^aeiouy]*$)/g); return (m && m.length) ? m : [word]; }
function fitLine(pi){ snap(); const ph = phrases()[pi]; const text = el('line' + pi).value; const words = text.match(/[A-Za-z']+/g) || []; const sy = []; words.forEach(w => { const parts = sylls(w); parts.forEach(s => sy.push({text: parts.length > 1 ? s : w, word: w})); });
  const sl = slots(); let si = 0; ph.forEach((k, j) => { const r = rows[k]; if (!sl[k] && j > 0) { r.text = '~'; r.kind = 'slur'; } else if (si < sy.length) { r.text = sy[si].text; r.word = sy[si].word; r.kind = 'note'; si++; } else { const prev = rows[ph[j-1]]; r.text = (j > 0 && r.t - prev.end <= 1.0) ? '~' : ''; r.kind = r.text ? 'slur' : 'unsung'; } });
  el('left' + pi).textContent = si < sy.length ? 'left out: ' + sy.slice(si).map(s => s.text).join(' ') : ''; render(); }
function select(i){ sel = Math.max(0, Math.min(rows.length - 1, i)); render(false); const n = document.querySelector('.note.sel'); if (n) n.scrollIntoView({inline: 'center', block: 'nearest', behavior: 'smooth'}); }
function render(full = true){
  const tl = el('timeline'); tl.querySelectorAll('.note,.phr').forEach(n => n.remove()); const ruler = el('ruler'); ruler.innerHTML = '';
  const t0 = DATA.audio_start; const tEnd = Math.max(...rows.map(r => r.end)) + 2; const W = (tEnd - t0) * PX + 40; tl.style.width = W + 'px';
  const lo = Math.min(...rows.map(r => r.pitch)) - 1, hi = Math.max(...rows.map(r => r.pitch)) + 1; const H = 380, top = 40; const yOf = p => top + (hi - p) / (hi - lo) * (H - 60);
  for (let s = Math.ceil(t0); s < tEnd; s++) { const d = document.createElement('div'); d.className = 'tick'; d.style.left = ((s - t0) * PX) + 'px'; d.textContent = s + 's'; ruler.appendChild(d); }
  const seenBars = new Set(); rows.forEach(r => { if (r.bar != null && r.beat != null && Math.abs(r.beat - 1) < 0.15 && !seenBars.has(r.bar)) { seenBars.add(r.bar); const d = document.createElement('div'); d.className = 'tick bar'; d.style.left = ((r.t - t0) * PX) + 'px'; d.style.top = '11px'; d.style.height = '11px'; d.textContent = 'bar ' + r.bar; ruler.appendChild(d); } });
  const ph = phrases(); const sl = slots(); const warns = [];
  ph.forEach((p, pi) => { const d = document.createElement('div'); d.className = 'phr'; d.style.left = ((rows[p[0]].t - t0) * PX - 6) + 'px'; d.innerHTML = '<span>phrase ' + (pi + 1) + ' · ' + p.length + ' notes · ' + p.filter(k => sl[k]).length + ' can carry a syllable</span>'; tl.appendChild(d); });
  rows.forEach((r, k) => { const n = document.createElement('div'); const dur = r.end - r.t; const tooShort = r.kind === 'note' && dur < DATA.short && !(k + 1 < rows.length && rows[k+1].kind === 'slur');
    n.className = 'note ' + (r.kind === 'slur' ? 'hold' : r.kind === 'unsung' ? 'unsung' : '') + (k === sel ? ' sel' : '') + (tooShort ? ' warn' : '') + (dur * PX < 48 ? ' narrow' : '');
    n.style.left = ((r.t - t0) * PX) + 'px'; n.style.width = Math.max(14, dur * PX - 2) + 'px'; n.style.top = yOf(r.pitch) + 'px';
    n.innerHTML = '<span>' + (r.text === '' ? '·' : r.text) + '</span><span class="lab">' + nameOf(r.pitch) + ' <span class="mute">' + dur.toFixed(2) + 's</span></span>';
    n.title = (r.bar != null ? 'bar ' + r.bar + ':' + Number(r.beat).toFixed(1) + ' · ' : '') + r.t.toFixed(2) + 's · ' + (r.placed || ''); n.onclick = () => select(k); n.ondblclick = () => { select(k); el('selText').focus(); };
    tl.appendChild(n); if (tooShort) warns.push('note ' + (k + 1) + ' (' + nameOf(r.pitch) + ' at ' + r.t.toFixed(1) + 's, ' + dur.toFixed(2) + 's): "' + r.text + '" is on a note too short to sing; hold it on the previous syllable or split a longer note instead'); });
  ph.forEach((p, pi) => { const want = (DATA.lines[pi] || '').match(/[A-Za-z']+/g) || []; const n = want.reduce((a, w) => a + sylls(w).length, 0); const have = p.filter(k => sl[k]).length; if (n > have) warns.push('phrase ' + (pi + 1) + ': the line has about ' + n + ' syllables for ' + have + ' notes that can carry one'); });
  el('warns').innerHTML = warns.length ? warns.map(w => '<li class="warn">' + w + '</li>').join('') : '<li class="mute">none</li>';
  const r = rows[sel]; el('selInfo').textContent = '— ' + (sel + 1) + ' of ' + rows.length + ', ' + nameOf(r.pitch) + (r.bar != null ? ', bar ' + r.bar + ':' + Number(r.beat).toFixed(1) : '') + ', ' + r.t.toFixed(2) + '–' + r.end.toFixed(2) + ' s'; el('selText').value = r.text;
  el('status').textContent = rows.filter(x => x.kind === 'note').length + ' sung · ' + rows.filter(x => x.kind === 'slur').length + ' held · ' + rows.filter(x => x.kind === 'unsung').length + ' unsung · ' + ph.length + ' phrases';
  if (full) { const L = el('lines'); L.innerHTML = ''; ph.forEach((p, pi) => { const d = document.createElement('div'); d.className = 'line'; const have = p.filter(k => sl[k]).length; const text = DATA.lines[pi] || p.filter(k => rows[k].kind === 'note').map(k => rows[k].text).join(' ');
    d.innerHTML = '<span class="mute">phrase ' + (pi + 1) + '</span><input id="line' + pi + '" value="' + text.replace(/"/g, '&quot;') + '"><button onclick="fitLine(' + pi + ')">fit</button><span class="cnt" id="left' + pi + '"></span>'; L.appendChild(d); }); }
}
const piano = el('piano'), voice = el('voice'), ref = el('ref'); let stopAt = null;
function clampT(t){ const d = isFinite(piano.duration) && piano.duration > 0 ? piano.duration : 50; return Math.max(0, Math.min(d, t)); }
function seek(t){ t = clampT(t); piano.currentTime = t; if (voice) voice.currentTime = t; if (ref) ref.currentTime = t; stopAt = null; updateClock(); }
function seekRel(d){ seek(piano.currentTime + d); }
function updateClock(){ const t = piano.currentTime; el('scrub').value = t; let bar = ''; for (const r of rows) { if (r.bar != null && r.t - DATA.audio_start <= t) bar = ' · bar ' + r.bar + ':' + Math.max(1, Math.round(Number(r.beat))); } el('clock').textContent = (DATA.audio_start + t).toFixed(1) + ' s' + bar; }
function toggle(){ if (piano.paused) { play(piano.currentTime); } else { pause(); } }
function play(from){ stopAt = null; piano.currentTime = from; piano.muted = !el('pianoOn').checked; piano.play(); if (voice) { voice.currentTime = from; voice.muted = !(el('voiceOn') && el('voiceOn').checked); voice.play(); } if (ref) { ref.currentTime = from; ref.muted = !(el('refOn') && el('refOn').checked); ref.play(); } el('playBtn').textContent = '❚❚ pause'; }
function pause(){ piano.pause(); if (voice) voice.pause(); if (ref) ref.pause(); el('playBtn').textContent = '▶ play'; }
document.addEventListener('change', e => { if (e.target.id === 'pianoOn') piano.muted = !e.target.checked; if (e.target.id === 'voiceOn' && voice) voice.muted = !e.target.checked; if (e.target.id === 'refOn' && ref) ref.muted = !e.target.checked; });
function playFrom(i){ play(Math.max(0, rows[i].t - DATA.audio_start - 0.1)); }
function playPhrase(){ const p = phrases().find(q => q.includes(sel)); play(Math.max(0, rows[p[0]].t - DATA.audio_start - 0.1)); stopAt = rows[p[p.length-1]].end - DATA.audio_start + 0.3; }
function tick(){ const x = (piano.currentTime) * PX; el('playhead').style.left = x + 'px'; if (stopAt != null && piano.currentTime >= stopAt) pause(); if (!piano.paused) { const w = el('wrap'); if (x < w.scrollLeft || x > w.scrollLeft + w.clientWidth - 40) w.scrollLeft = x - 80; updateClock(); } requestAnimationFrame(tick); }
piano.onended = pause; piano.onloadedmetadata = () => { el('scrub').max = piano.duration; updateClock(); }; if (isFinite(piano.duration) && piano.duration > 0) el('scrub').max = piano.duration; requestAnimationFrame(tick);
el('timeline').addEventListener('click', e => { if (e.target.closest('.note')) return; const rect = el('timeline').getBoundingClientRect(); seek((e.clientX - rect.left) / PX); });
document.addEventListener('keydown', e => { const typing = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA'; if (typing && e.key !== 'Escape') return;
  if (e.key === 'ArrowRight' && e.shiftKey) { shift(sel, 1); e.preventDefault(); } else if (e.key === 'ArrowLeft' && e.shiftKey) { shift(sel, -1); e.preventDefault(); }
  else if (e.key === 'ArrowRight') { select(sel + 1); e.preventDefault(); } else if (e.key === 'ArrowLeft') { select(sel - 1); e.preventDefault(); }
  else if (e.key === 'Enter') { el('selText').focus(); el('selText').select(); e.preventDefault(); } else if (e.key === ' ') { piano.paused ? playFrom(sel) : pause(); e.preventDefault(); }
  else if (e.key === 'h' || e.key === 'H') hold(sel); else if (e.key === 'u' || e.key === 'U') mute(sel); else if (e.key === 's' || e.key === 'S') split(sel); else if (e.key === 'm' || e.key === 'M') merge(sel);
  else if ((e.ctrlKey || e.metaKey) && e.key === 'z') { undo(); e.preventDefault(); } else if ((e.ctrlKey || e.metaKey) && e.key === 'y') { redo(); e.preventDefault(); } else if (e.key === 'Escape') e.target.blur(); });
el('selText').addEventListener('keydown', e => { if (e.key === 'Enter') { setText(sel, e.target.value); select(sel + 1); e.preventDefault(); } });
function payload(){ return {source: DATA.source, edited_at: new Date().toISOString(), note: el('note').value, lines: phrases().map((p, pi) => el('line' + pi) ? el('line' + pi).value : ''),
  rows: rows.map((r, k) => ({index: k, t: r.t, end: r.end, pitch: r.pitch, bar: r.bar, beat: r.beat, text: r.text, kind: r.kind, word: r.word, placed: r.placed || null}))}; }
function banner(msg, ok){ el('banner').innerHTML = (ok ? '<b>✓</b> ' : '') + msg; }
function download(){ const blob = new Blob([JSON.stringify(payload(), null, 1)], {type: 'application/json'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'lyric-fit.edited.json'; a.click(); }
async function copyJson(){ const txt = JSON.stringify(payload(), null, 1); try { await navigator.clipboard.writeText(txt); banner('Copied the fit as JSON. Paste it to the agent if Save is unavailable.', true); } catch (e) { const ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select(); banner('Clipboard refused; the JSON is selected below, copy it by hand.'); } }
async function save(){ const btn = el('saveBtn'); btn.disabled = true;
  try { if (!window.claude || !window.claude.use) { download(); banner('Downloaded lyric-fit.edited.json. Send it to the agent.', true); return; }
    const db = await claude.use('db'); if (!db) { banner('This view cannot reach the page store (sign in, or open the link in claude.ai). Use copy JSON instead.'); return; }
    const out = payload(); await db.doc(DATA.store_doc).set(out); try { await db.collection(DATA.store_doc + '/versions').add(out); } catch (e) {}
    banner('Saved at ' + new Date().toLocaleTimeString() + '. The agent can read this version now; every later Save replaces it.', true); }
  catch (e) { banner('Save failed (' + (e && (e.code || e.message)) + '). Use copy JSON and paste it to the agent.'); }
  finally { btn.disabled = false; } }
(async () => { if (!window.claude || !window.claude.use) return; const db = await claude.use('db'); if (!db) return; let first = true;
  db.doc(DATA.store_doc).onSnapshot(sn => { if (!first) return; first = false; if (!sn.exists) return; const d = sn.data(); if (!d || !Array.isArray(d.rows) || !(d.edited_at > DATA.generated_at)) return;
    rows = d.rows.map(r => ({t: r.t, end: r.end, pitch: r.pitch, bar: r.bar, beat: r.beat, text: r.text || '', kind: r.kind || kindOf(r.text), word: r.word, placed: r.placed || 'performance'})); sel = 0;
    if (Array.isArray(d.lines)) DATA.lines = d.lines; el('note').value = d.note || ''; render(); banner('Loaded your saved edit from ' + new Date(d.edited_at).toLocaleString() + '. Reset returns to the fitted version.', true); }, e => {}); })();
render();
</script></body></html>"""
    page = (page.replace("__TITLE__", html.escape(a.title)).replace("__AUDIO__", src_of(a.audio)).replace("__VOICEEL__", voice_el).replace("__TAILOPEN__", tail_open)
                .replace("__VOICEBTN__", voice_btn).replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__SAVELABEL__", "Save" if a.artifact else "Save lyric-fit.edited.json"))
    if a.artifact:   # the viewer never allows a page-started download: the fallback there is the clipboard
        page = page.replace("</script></body></html>", "</script>")
        page = page.replace("if (!window.claude || !window.claude.use) { download(); banner('Downloaded lyric-fit.edited.json. Send it to the agent.', true); return; }", "if (!window.claude || !window.claude.use) { await copyJson(); return; }")
        page = page.replace("function download(){ const blob = new Blob([JSON.stringify(payload(), null, 1)], {type: 'application/json'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'lyric-fit.edited.json'; a.click(); }\n", "")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(page, encoding="utf-8")
    print(f"wrote {a.out}: {len(rows)} notes")


if __name__ == "__main__":
    main()
