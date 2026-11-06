#!/usr/bin/env python3
"""recorder.py — a piano to play the vocal line on, in time with the recording (/arrange-lyrics; plain python).

    python recorder.py --analysis piano-analysis.json --audio piano-0s-65s.mp3 --audio-start 0 -o recorder.html [--artifact]

The composer picks a bar, gets two bars of the recording as a count-in (with a
click on every beat of the composer's feel if wanted), and plays the line on the
computer keyboard or the on-screen keys while the recording plays. Notes are
snapped to sixteenths of the composer's beat on the measured grid and shown as the composer's
shorthand (C4/ half a beat, A4*4 four beats, z2 two beats of rest) with the
notated bar, and as a small piano roll. Play back over the recording; Save
writes the take to the page's store (takes/<id>) for /arrange-lyrics to read;
Copy gives the shorthand as text.
"""
import argparse, base64, html, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent)); from feel import feel, subdivision  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", required=True); ap.add_argument("--audio", required=True); ap.add_argument("--audio-start", type=float, default=0.0)
    ap.add_argument("-o", "--out", required=True); ap.add_argument("--artifact", action="store_true"); ap.add_argument("--title", default="Play the Line")
    ap.add_argument("--duration", type=float, default=65.0, help="seconds of audio in the page (after --audio-start)"); ap.add_argument("--start-bar", type=int, default=1)
    ap.add_argument("--grid", help="the composer's saved beat taps (grid/current.json), built into the page")
    a = ap.parse_args()
    an = json.load(open(a.analysis)); clk = Clock(an)
    per, bpb, ts = feel(an)   # the composer's beats per map beat; the composer's beats per notated bar
    grid = []
    for i, b in enumerate(clk.beats):
        nxt = clk.beats[i + 1]["t"] if i + 1 < len(clk.beats) else b["t"] + clk.last_dur
        o = clk._ordinal(b["bar"], b["beat"])
        for k in range(per):
            on = o * per + k                # the composer's beats since the first downbeat
            grid.append({"t": round(b["t"] + (nxt - b["t"]) * k / per, 4), "bar": int(on // bpb) + 1, "beat": int(on % bpb) + 1, "on": on})
    src = ("data:audio/mpeg;base64," + base64.b64encode(Path(a.audio).read_bytes()).decode()) if a.artifact else html.escape(Path(a.audio).name)
    dur = a.audio_start + a.duration
    data = {"grid": [g for g in grid if g["t"] <= dur + 2], "audio_start": a.audio_start, "bpb": bpb, "ts": ts, "sub": subdivision(ts)}
    if a.grid:   # the composer's saved taps, for a copy that cannot reach the page store
        g = json.load(open(a.grid)); data["saved_grid"] = {"offset_ms": g.get("offset_ms", 0), "taps": g.get("taps", [])}
    head = (f"<title>{html.escape(a.title)}</title>\n<meta name=\"claude:viewport-fit-sides\" content=\"cover\">\n" if a.artifact
            else f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(a.title)}</title>\n')
    page = head + r"""<style>
:root{--bg:#f7f5f0;--ink:#1d1c1a;--mute:#6f6a62;--line:#ddd7cc;--panel:#efebe3;--acc:#2f6f9f;--rec:#c0392b;--white:#fffdf8;--black:#222}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31;--panel:#1f1f24;--acc:#6aa6d6;--rec:#ef6b5e;--white:#e9e6df;--black:#111;color-scheme:dark}}
:root[data-theme=dark]{--bg:#17171a;--ink:#ecebe6;--mute:#a09c93;--line:#2c2c31;--panel:#1f1f24;--acc:#6aa6d6;--rec:#ef6b5e;--white:#e9e6df;--black:#111;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
#app{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:12px;max-width:1100px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}.mute{color:var(--mute)}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0}
button,select,input{font:inherit}button{padding:7px 12px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink);cursor:pointer}
button.rec{background:var(--rec);color:#fff;border-color:var(--rec)}button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
select,input[type=number]{padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)}
#status{font-family:ui-monospace,Menlo,monospace;font-size:14px}
.kb{position:relative;height:150px;user-select:none;touch-action:none;margin:8px 0;overflow-x:auto}.kbin{position:relative;height:100%}
.w,.b{position:absolute;top:0;border:1px solid var(--line);border-radius:0 0 5px 5px;display:flex;align-items:flex-end;justify-content:center;font-size:11px;padding-bottom:6px;cursor:pointer}
.w{background:var(--white);color:#555;height:100%;width:42px;z-index:1}.b{background:var(--black);color:#bbb;height:62%;width:28px;z-index:2}
.w.on{background:#bcd7ee}.b.on{background:var(--acc)}
#roll{width:100%;height:140px;background:var(--panel);border-radius:6px;display:block}
pre{background:var(--panel);padding:10px;border-radius:6px;white-space:pre-wrap;word-break:break-word;font-size:14px}
kbd{border:1px solid var(--line);border-radius:3px;padding:0 4px;font-size:12px;background:var(--panel)}
</style>
<div id="app"><h1>__TITLE__</h1>
<p class="mute">If the clicks don't sit on the piano, nudge them, or press <b>Tap the beat</b> and tap <kbd>T</kbd> on every beat while it plays: your taps become the grid for those bars. Pick a bar, press <b>Record</b>, listen to two bars of count-in, then play the line on the keys while the recording plays. Notes snap to __SNAP__ of your beat. Bars are the notated bars on the score canvas.</p>
<div class="row">Start at bar <input type="number" id="bar" value="__STARTBAR__" min="1" max="400" style="width:70px"> <label><input type="checkbox" id="click" checked> click on every beat</label>
<label><input type="checkbox" id="pianoOn" checked> piano recording</label>
<button class="rec" id="recBtn">● Record</button><button id="stopBtn">■ Stop</button><button id="playBtn">▶ Play back</button><button id="clearBtn">Clear</button></div>
<div class="row"><b>Beat grid</b> <button id="nE50">◀◀ 50 ms earlier</button><button id="nE10">◀ 10 ms</button><span id="offs" style="font-family:ui-monospace,Menlo,monospace;min-width:70px;text-align:center">0 ms</span><button id="nL10">10 ms ▶</button><button id="nL50">50 ms later ▶▶</button>
<button id="tapBtn">Tap the beat (T)</button><button id="tapClear">Use the measured grid</button><span id="tapInfo" class="mute"></span></div>
<div class="row"><button id="midiBtn">Connect MIDI keyboard</button><span id="midi" class="mute">A MIDI keyboard plays the line; its pads (channel 10) tap the beat.</span></div>
<div id="status" class="mute">ready</div>
<div class="kb" id="kb"><div class="kbin" id="kbin"></div></div>
<p class="mute" style="font-size:13px">Computer keys: <kbd>A</kbd>=C <kbd>W</kbd>=C# <kbd>S</kbd>=D <kbd>E</kbd>=Eb <kbd>D</kbd>=E <kbd>F</kbd>=F <kbd>T</kbd>=F# <kbd>G</kbd>=G <kbd>Y</kbd>=Ab <kbd>H</kbd>=A <kbd>U</kbd>=Bb <kbd>J</kbd>=B <kbd>K</kbd>=C <kbd>O</kbd>=C# <kbd>L</kbd>=D <kbd>P</kbd>=Eb <kbd>;</kbd>=E <kbd>'</kbd>=F · <kbd>Z</kbd>/<kbd>X</kbd> octave down/up (now <span id="oct">C4</span>)</p>
<canvas id="roll" width="1060" height="140"></canvas>
<h2 style="font-size:15px">Your line, as shorthand</h2>
<pre id="out">nothing recorded yet</pre>
<div class="row"><input id="words" placeholder="the words for this line (optional)" style="flex:1;min-width:200px;padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)">
<button class="primary" id="saveBtn">Save take</button><button id="copyBtn">Copy</button></div>
<div id="msg" class="mute"></div></div>
<audio id="piano" preload="auto" src="__SRC__"></audio>
<script>
if (window.__playTheLineLoaded) { throw new Error('already loaded'); } window.__playTheLineLoaded = true;   // a live update must not add a second set of key listeners
const DATA = __DATA__; const BPB = DATA.bpb || 4; const G0 = DATA.grid; let G = G0.map(g => ({...g}));
let offsetMs = 0, taps = [], tapping = false, tapRange = null;
function rebuild(){ G = G0.map(g => ({...g, t: g.t + offsetMs / 1000}));
  if (taps.length >= 2) { // snap the first tap to the nearest beat of the grid, then each later tap is the next beat
    let i = 0, best = 1e9; G.forEach((g, k) => { const d = Math.abs(g.t - taps[0]); if (d < best) { best = d; i = k; } });
    taps.forEach((t, k) => { if (G[i + k]) G[i + k].t = t; });
    // beats after the last tap keep their spacing, shifted by the last tap's change
    const last = i + taps.length - 1, shift = G[last] ? taps[taps.length - 1] - (G0[last].t + offsetMs / 1000) : 0;
    for (let k = last + 1; k < G.length; k++) G[k].t = G0[k].t + offsetMs / 1000 + shift;
    tapRange = [G[i].bar, G[last].bar]; el('tapInfo').textContent = `your ${taps.length} taps set the beats of bars ${tapRange[0]}–${tapRange[1]}`; }
  else { tapRange = null; el('tapInfo').textContent = ''; }
  el('offs').textContent = (offsetMs > 0 ? '+' : '') + offsetMs + ' ms'; render(); }
function persist(){ (async () => { try { const db = window.claude && claude.use ? await claude.use('db') : null; if (!db) return; await db.doc('grid/current').set({offset_ms: offsetMs, taps: taps.map(t => +t.toFixed(3)), saved_at: new Date().toISOString(), tapped_bars: tapRange}); } catch (e) {} })(); }
const NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
const el = id => document.getElementById(id); const piano = el('piano');
let ac = null, base = 60, notes = [], held = {}, recording = false, t0wall = 0, t0audio = 0, raf = null, stopAt = null;
function ctx(){ if (!ac) ac = new (window.AudioContext || window.webkitAudioContext)(); if (ac.state === 'suspended') ac.resume(); return ac; }
function tone(m, dur = 0.6, gain = 0.25){ const c = ctx(); const t = c.currentTime; const f = 440 * Math.pow(2, (m - 69) / 12);
  const o1 = c.createOscillator(), o2 = c.createOscillator(), g = c.createGain(); o1.type = 'triangle'; o2.type = 'sine'; o1.frequency.value = f; o2.frequency.value = f * 2;
  const g2 = c.createGain(); g2.gain.value = 0.25; o2.connect(g2).connect(g); o1.connect(g); g.connect(c.destination);
  g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(gain, t + 0.01); g.gain.exponentialRampToValueAtTime(0.001, t + dur);
  o1.start(t); o2.start(t); o1.stop(t + dur + 0.05); o2.stop(t + dur + 0.05); return {g, o1, o2}; }
function click(strong){ const c = ctx(); const t = c.currentTime; const o = c.createOscillator(), g = c.createGain(); o.frequency.value = strong ? 1500 : 1000; g.gain.setValueAtTime(strong ? 0.25 : 0.12, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.05); o.connect(g).connect(c.destination); o.start(t); o.stop(t + 0.06); }
// keyboard
const LOW = 55, HIGH = 81; const kbin = el('kbin'); const isBlack = m => [1,3,6,8,10].includes(m % 12); const keyEls = {};
(function build(){ let x = 0; for (let m = LOW; m <= HIGH; m++) { if (isBlack(m)) continue; const d = document.createElement('div'); d.className = 'w'; d.style.left = x + 'px'; d.textContent = NAMES[m % 12] + (Math.floor(m / 12) - 1); d.dataset.m = m; kbin.appendChild(d); keyEls[m] = d;
    if (isBlack(m + 1) && m + 1 <= HIGH) { const b = document.createElement('div'); b.className = 'b'; b.style.left = (x + 28) + 'px'; b.dataset.m = m + 1; kbin.appendChild(b); keyEls[m + 1] = b; } x += 42; } kbin.style.width = x + 'px'; })();
function now(){ return recording ? (piano.paused ? (t0audio + (performance.now() - t0wall) / 1000) : piano.currentTime + DATA.audio_start) : null; }
const lastDown = {};
function down(m){ if (held[m]) return; const nowMs = performance.now(); if (lastDown[m] && nowMs - lastDown[m] < 60) return; lastDown[m] = nowMs; const v = tone(m, 1.2); held[m] = {v, t: now()}; if (keyEls[m]) keyEls[m].classList.add('on'); }
function up(m){ const h = held[m]; if (!h) return; delete held[m]; if (keyEls[m]) keyEls[m].classList.remove('on'); const t = now(); if (h.t != null && t != null && t > h.t + 0.03) { notes.push({m, t: h.t, end: t}); render(); } }
kbin.addEventListener('pointerdown', e => { const m = +e.target.dataset.m; if (m) { e.preventDefault(); down(m); const u = () => { up(m); window.removeEventListener('pointerup', u); }; window.addEventListener('pointerup', u); } });
const KEYS = {a:0,w:1,s:2,e:3,d:4,f:5,t:6,g:7,y:8,h:9,u:10,j:11,k:12,o:13,l:14,p:15,';':16,"'":17};
document.addEventListener('keydown', e => { if (e.target.tagName === 'INPUT') return; const k = e.key.toLowerCase(); if (e.repeat) return;
  if (k === 't' && tapping) { e.preventDefault(); taps.push(piano.currentTime + DATA.audio_start); click(false); el('tapInfo').textContent = taps.length + ' taps'; return; }
  if (k === 'z') { base = Math.max(48, base - 12); el('oct').textContent = 'C' + (base / 12 - 1); return; } if (k === 'x') { base = Math.min(72, base + 12); el('oct').textContent = 'C' + (base / 12 - 1); return; }
  if (k in KEYS) { e.preventDefault(); down(base + KEYS[k]); } });
document.addEventListener('keyup', e => { const k = e.key.toLowerCase(); if (k in KEYS) up(base + KEYS[k]); });
// a MIDI keyboard through the browser (Web MIDI): keys play the line, drum pads (channel 10) tap the beat
let midiAcc = null;
function midiTap(){ if (!tapping) return; taps.push(piano.currentTime + DATA.audio_start); click(false); el('tapInfo').textContent = taps.length + ' taps'; }
function onMidi(ev){ const st = ev.data[0], d1 = ev.data[1], d2 = ev.data[2]; const type = st & 0xf0, ch = st & 0x0f;
  if (type === 0x90 && d2 > 0) { if (ch === 9) { midiTap(); return; } down(d1); }
  else if (type === 0x80 || (type === 0x90 && d2 === 0)) { if (ch !== 9) up(d1); } }
function midiAttach(){ const names = []; midiAcc.inputs.forEach(i => { i.onmidimessage = onMidi; names.push(i.name); });
  el('midi').textContent = names.length ? 'MIDI connected: ' + names.join(', ') + '. Keys play the line; pads tap the beat while Tap the beat is on.' : 'MIDI is allowed, but no keyboard is connected. Plug it in; it is picked up automatically.'; }
function midiConnect(){ if (!navigator.requestMIDIAccess) { el('midi').textContent = 'This browser has no MIDI support. Use Chrome or Edge.'; return; }
  el('midi').textContent = 'asking the browser for MIDI...';
  navigator.requestMIDIAccess().then(acc => { midiAcc = acc; midiAttach(); acc.onstatechange = midiAttach; },
    err => { el('midi').textContent = 'MIDI was blocked here (' + ((err && (err.name || err.message)) || err) + '). The page frame may not allow MIDI; ask the agent for the standalone copy.'; }); }
el('midiBtn').onclick = midiConnect;
try { navigator.permissions && navigator.permissions.query({name: 'midi'}).then(st => { if (st.state === 'granted') midiConnect(); }).catch(() => {}); } catch (e) {}
// grid helpers: the composer's beats
function onAt(t){ let i = 0; while (i + 1 < G.length && G[i + 1].t <= t) i++; const a = G[i], b = G[Math.min(i + 1, G.length - 1)]; const span = (b.t - a.t) || 1; return a.on + Math.max(0, Math.min(1, (t - a.t) / span)) * (b.on - a.on || 1); }
function tAtBarBeat(bar){ const g = G.find(x => x.bar === bar && x.beat === 1); return g ? g.t : null; }
const SUB = DATA.sub || 4; const q = x => Math.round(x * SUB) / SUB;
function len(x){ if (Math.abs(x - 1) < 1e-6) return ''; if (Math.abs(x - 1/3) < 1e-6) return '/3'; if (Math.abs(x - 2/3) < 1e-6) return '*2/3'; if (Math.abs(x - 0.5) < 1e-6) return '/'; if (Math.abs(x - 0.25) < 1e-6) return '//'; return '*' + (+x.toFixed(2)); }
function shorthand(){ if (!notes.length) return {text: 'nothing recorded yet', rows: []};
  const ns = notes.slice().sort((a, b) => a.t - b.t).map(n => ({...n, on: q(onAt(n.t)), off: q(onAt(n.end))})).map(n => ({...n, off: Math.max(n.off, n.on + 0.25)}));
  for (let i = 0; i + 1 < ns.length; i++) if (ns[i].off > ns[i + 1].on) ns[i].off = Math.max(ns[i].on + 0.25, ns[i + 1].on);
  const startBar = Math.floor(ns[0].on / BPB) + 1; let pos = (startBar - 1) * BPB; const toks = []; let lastBar = startBar;
  for (const n of ns) { const bar = Math.floor(n.on / BPB) + 1; if (bar !== lastBar) { toks.push('|'); lastBar = bar; } if (n.on > pos + 1e-6) toks.push('z' + len(n.on - pos)); toks.push(NAMES[n.m % 12] + (Math.floor(n.m / 12) - 1) + len(n.off - n.on)); pos = n.off; }
  const s0 = G.find(g => Math.abs(g.on - (startBar - 1) * BPB) < 1e-6);
  return {text: `bar ${startBar} (${s0 ? s0.t.toFixed(2) : '?'} s): ` + toks.join(' ').replace(/z\*(\d+(?:\.\d+)?)/g, 'z$1'), rows: ns, startBar, startT: s0 ? s0.t : null}; }
function render(){ const sh = shorthand(); el('out').textContent = sh.text; const cv = el('roll'), c = cv.getContext('2d'); c.clearRect(0, 0, cv.width, cv.height);
  if (!sh.rows.length) return; const lo = Math.min(...sh.rows.map(n => n.m)) - 2, hi = Math.max(...sh.rows.map(n => n.m)) + 2; const a0 = (sh.startBar - 1) * BPB, a1 = Math.max(...sh.rows.map(n => n.off)) + 1; const X = on => 10 + (on - a0) / (a1 - a0) * (cv.width - 20), Y = m => 10 + (hi - m) / (hi - lo) * (cv.height - 20);
  c.strokeStyle = getComputedStyle(document.body).getPropertyValue('--line'); for (let b = a0; b <= a1; b++) { c.lineWidth = b % BPB === 0 ? 1.5 : 0.5; c.beginPath(); c.moveTo(X(b), 0); c.lineTo(X(b), cv.height); c.stroke(); if (b % BPB === 0) { c.fillStyle = '#888'; c.fillText('bar ' + (b / BPB + 1), X(b) + 3, 10); } }
  c.fillStyle = getComputedStyle(document.body).getPropertyValue('--acc'); for (const n of sh.rows) { c.fillRect(X(n.on), Y(n.m) - 4, Math.max(3, X(n.off) - X(n.on) - 1), 8); c.fillText(NAMES[n.m % 12] + (Math.floor(n.m / 12) - 1), X(n.on), Y(n.m) - 6); } }
// transport
let lastBeat = -1;
function loop(){ const t = recording ? now() : (piano.paused ? null : piano.currentTime + DATA.audio_start); if (t != null) { const i = G.findIndex(g => g.t > t) - 1; if (i >= 0 && i !== lastBeat) { lastBeat = i; if (el('click').checked) click(G[i].beat === 1); }
    const g = G[Math.max(0, i)]; el('status').textContent = (recording ? '● recording · ' : '▶ ') + t.toFixed(2) + ' s · bar ' + g.bar + ' beat ' + g.beat; if (stopAt && t >= stopAt) stop(); }
  raf = requestAnimationFrame(loop); }
function start(record){ const bar = Math.max(1, +el('bar').value || 1); const tb = tAtBarBeat(bar); if (tb == null) { el('msg').textContent = 'That bar is outside the recording on this page (bars 1 to ' + G[G.length - 1].bar + ').'; return; }
  const ci = tAtBarBeat(Math.max(1, bar - 2)) ?? 0; ctx(); piano.muted = !el('pianoOn').checked; piano.currentTime = Math.max(0, ci - DATA.audio_start); lastBeat = -1; stopAt = null;
  recording = record; if (record) { t0audio = ci; t0wall = performance.now(); } piano.play().catch(() => {}); el('recBtn').textContent = record ? '● Recording…' : '● Record'; if (!raf) loop(); }
function stop(){ recording = false; piano.pause(); stopAt = null; Object.keys(held).forEach(m => up(+m)); el('recBtn').textContent = '● Record'; el('status').textContent = 'stopped'; render(); }
el('recBtn').onclick = () => start(true); el('stopBtn').onclick = () => { const wasTapping = tapping; tapping = false; el('tapBtn').textContent = 'Tap the beat (T)'; stop(); if (wasTapping) { rebuild(); persist(); } };
[['nE50', -50], ['nE10', -10], ['nL10', 10], ['nL50', 50]].forEach(([id, d]) => el(id).onclick = () => { offsetMs += d; rebuild(); persist(); });
el('tapBtn').onclick = () => { taps = []; tapping = true; el('tapBtn').textContent = 'Tapping… press T on every beat, Stop when done'; el('click').checked = false; start(false); };
el('tapClear').onclick = () => { taps = []; offsetMs = 0; rebuild(); persist(); };
function useSavedGrid(){ if (DATA.saved_grid && DATA.saved_grid.taps && DATA.saved_grid.taps.length) { offsetMs = DATA.saved_grid.offset_ms || 0; taps = DATA.saved_grid.taps.slice(); rebuild(); el('msg').textContent = 'Using your saved beat taps.'; } }
(async () => { try { const db = window.claude && claude.use ? await claude.use('db') : null; if (!db) { useSavedGrid(); return; } const sn = await db.doc('grid/current').get(); if (sn.exists) { const d = sn.data(); offsetMs = d.offset_ms || 0; taps = d.taps || []; rebuild(); el('msg').textContent = 'Loaded your beat grid settings.'; } } catch (e) {} })();
el('clearBtn').onclick = () => { notes = []; render(); el('msg').textContent = ''; };
el('playBtn').onclick = () => { const sh = shorthand(); if (!sh.rows.length) return; const first = sh.rows[0].t; el('bar').value = sh.startBar; start(false); const lead = (first - (tAtBarBeat(Math.max(1, sh.startBar - 2)) ?? 0)); const t0 = performance.now();
  sh.rows.forEach(n => setTimeout(() => tone(n.m, Math.min(2.5, n.end - n.t + 0.2), 0.3), (n.t - (tAtBarBeat(Math.max(1, sh.startBar - 2)) ?? 0)) * 1000)); stopAt = sh.rows[sh.rows.length - 1].end + 1.5; };
el('copyBtn').onclick = async () => { const sh = shorthand(); const txt = sh.text + (el('words').value ? '  |  ' + el('words').value : ''); try { await navigator.clipboard.writeText(txt); el('msg').textContent = 'Copied. Paste it into the chat.'; } catch (e) { el('msg').textContent = 'Copy was refused; select the text above and copy it by hand.'; } };
el('saveBtn').onclick = async () => { const sh = shorthand(); if (!sh.rows.length) { el('msg').textContent = 'Record something first.'; return; }
  const id = 'take-' + new Date().toISOString().replace(/[:.]/g, '-');
  const take = {saved_at: new Date().toISOString(), shorthand: sh.text, words: el('words').value, start_bar: sh.startBar, start_t: sh.startT,
      notes: sh.rows.map(n => ({pitch: n.m, t: +n.t.toFixed(3), end: +n.end.toFixed(3), on: n.on, off: n.off})), grid_offset_ms: offsetMs, taps: taps.map(t => +t.toFixed(3))};
  const db = window.claude && claude.use ? await claude.use('db') : null;
  if (!db) {   // a standalone copy: hand the take over as a file (and on the clipboard)
    const blob = new Blob([JSON.stringify({id, take}, null, 1)], {type: 'application/json'}); const aEl = document.createElement('a'); aEl.href = URL.createObjectURL(blob); aEl.download = id + '.json'; document.body.appendChild(aEl); aEl.click(); aEl.remove();
    let copied = false; try { await navigator.clipboard.writeText('TAKE ' + JSON.stringify({id, take})); copied = true; } catch (e) {}
    el('msg').textContent = 'Saved to your Downloads as ' + id + '.json' + (copied ? ' and copied' : '') + '. Drop the file into the chat' + (copied ? ' or paste it' : '') + ' and say "take saved".'; return; }
  try { await db.collection('takes').doc(id).set(take); el('msg').textContent = 'Saved as ' + id + '. Tell the agent "take saved".'; }
  catch (e) { el('msg').textContent = 'Save failed (' + (e.code || e.message) + '); use Copy instead.'; } };
rebuild();
</script>"""
    page = page.replace("__TITLE__", html.escape(a.title)).replace("__SRC__", src).replace("__DATA__", json.dumps(data)).replace("__STARTBAR__", str(a.start_bar)).replace("__SNAP__", "thirds" if subdivision(ts) == 3 else "sixteenths")
    if not a.artifact:
        page = page.replace("<style>", "<style>", 1) + "</body></html>"
    Path(a.out).write_text(page, encoding="utf-8")
    print(f"wrote {a.out}: {len(data['grid'])} beats on the grid, {Path(a.out).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
