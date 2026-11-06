#!/usr/bin/env python3
"""versions.py — put other versions of a verse on one score canvas, behind version pills (/arrange-lyrics; plain python).

    python versions.py main/index.html --version "Take 18:26=other/index.html" [--piano piano.mp3] -o out.html

Each version is a canvas already built by canvas.py (its own score, lines, sounds,
revision log and sung mix). The main canvas stays the default; the others are
copied in hidden, each with its own audio, and a row of version pills switches
score, lines and audio together at the same point in the song. The voice pills
belong to the main version and are hidden while another version is shown.
With --piano, the "voice" checkbox works: unticked, the piano recording plays alone.
"""
import argparse, base64, re
from pathlib import Path

SCORE_START = '<div class="score" id="score">'
COLS_START = '<div class="cols">'
SCRIPT_START = '<script>'

UPLOAD_JS = """<script src="https://cdn.jsdelivr.net/npm/verovio@4.3.1/dist/verovio-toolkit-wasm.js" defer></script>
<script>
(function(){
  const OFF = __OFFSET__;   // the canvas's notation offset in the composer's beats
  const NAMES = ['C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B'];
  const ABCN = {0:'C',1:'^C',2:'D',3:'_E',4:'E',5:'F',6:'^F',7:'G',8:'_A',9:'A',10:'B',11:'=B'};   // key of F: B is flat unless marked natural
  function abcPitch(m){ const pc = m % 12, oct = Math.floor(m / 12) - 1; let n = ABCN[pc]; const base = n.replace(/[\\^_=]/g, ''), acc = n.slice(0, n.length - base.length);
    if (oct >= 5) return acc + base.toLowerCase() + "'".repeat(oct - 5); return acc + base + ",".repeat(Math.max(0, 4 - oct)); }
  function toAbc(notes){   // sixteenths of the composer's beat; bars of 4 beats
    const ev = notes.map(n => ({p: n.pitch, a: Math.round((n.on + OFF) * 4), b: Math.max(Math.round((n.on + OFF) * 4) + 1, Math.round((n.off + OFF) * 4))})).sort((x, y) => x.a - y.a);
    for (let i = 0; i + 1 < ev.length; i++) ev[i].b = Math.min(ev[i].b, ev[i + 1].a);
    const first = Math.floor(ev[0].a / 16) * 16, last = Math.ceil(ev[ev.length - 1].b / 16) * 16; let out = '', pos = first, bar = first;
    const emit = (tok, len) => { while (len > 0) { const room = bar + 16 - pos, l = Math.min(len, room); out += tok + l + ((tok !== 'z' && len > l) ? '-' : '') + ' '; pos += l; len -= l; if (pos === bar + 16) { out += '| '; bar += 16; } } };
    for (const e of ev) { if (e.a > pos) emit('z', e.a - pos); if (e.a < pos) continue; emit(abcPitch(e.p), e.b - e.a); }
    if (pos < last) emit('z', last - pos);
    return {abc: 'X:1\\nM:4/4\\nL:1/16\\nK:F\\n' + out + ']', firstBar: first / 16 + 1};
  }
  let tk = null; function toolkit(){ return new Promise(res => { if (tk) return res(tk); const go = () => { tk = new verovio.toolkit(); tk.setOptions({pageWidth: 2200, scale: 40, adjustPageHeight: true, breaks: 'auto', footer: 'none', header: 'none'}); res(tk); };
    const wait = () => (window.verovio && verovio.module) ? (verovio.module.calledRun ? go() : verovio.module.onRuntimeInitialized = go) : setTimeout(wait, 100); wait(); }); }
  let take = null, ac = null, timers = [];
  document.getElementById('takeFile').addEventListener('change', async ev => {
    const f = ev.target.files[0]; if (!f) return; const msg = document.getElementById('takeMsg');
    try { const d = JSON.parse(await f.text()); take = d.take || d; if (!take.notes || !take.notes.length) throw new Error('no notes in this file'); }
    catch (e) { msg.textContent = 'Could not read that file: ' + e.message; return; }
    const {abc, firstBar} = toAbc(take.notes); msg.textContent = f.name + ': ' + take.notes.length + ' notes from bar ' + firstBar + ' (engraving...)';
    let pill = document.querySelector('.vpill[data-v="up"]');
    if (!pill) { let row = document.querySelector('.vpills'); if (!row) { row = document.createElement('div'); row.className = 'pills vpills'; row.innerHTML = '<span class="mute" style="align-self:center">Version:</span><button class="vpill pill on" data-v="0">Current</button>'; document.getElementById('takeFile').closest('.bar').after(row);
        row.querySelector('[data-v="0"]').addEventListener('click', () => showV('0')); }
      pill = document.createElement('button'); pill.className = 'vpill pill'; pill.dataset.v = 'up'; row.appendChild(pill); pill.addEventListener('click', () => showV('up')); }
    pill.textContent = 'Uploaded: ' + f.name.replace(/\\.json$/, '').slice(-24);
    const lines = []; let cur = []; take.notes.forEach((n, i) => { if (i && n.t - take.notes[i - 1].end >= 1.0) { lines.push(cur); cur = []; } cur.push(n); }); if (cur.length) lines.push(cur);
    document.getElementById('upLines').innerHTML = lines.map(ln => '<li>starts ' + ln[0].t.toFixed(1) + ' s · ' + ln.map(n => NAMES[n.pitch % 12] + (Math.floor(n.pitch / 12) - 1)).join(' ') + '</li>').join('');
    showV('up');
    try { const t = await toolkit(); t.loadData(abc); document.getElementById('score-up').innerHTML = t.renderToSVG(1); msg.textContent = f.name + ': ' + take.notes.length + ' notes from bar ' + firstBar + '. Played as a tone; send it to the agent for words and singing.'; }
    catch (e) { document.getElementById('score-up').textContent = 'The engraver could not load (' + e + '); the notes are listed below.'; }
  });
  function showV(v){ document.querySelectorAll('section.ver').forEach(s => s.hidden = s.dataset.v !== v); document.querySelectorAll('.vpill').forEach(x => x.classList.toggle('on', x.dataset.v === v));
    const vp = document.getElementById('voicepills'); if (vp) vp.style.display = v === '0' ? '' : 'none'; if (v !== 'up') stopUp(); }
  document.querySelectorAll('.vpill:not([data-v="up"])').forEach(b => b.addEventListener('click', () => stopUp()));
  function stopUp(){ timers.forEach(clearTimeout); timers = []; const p = document.getElementById('piano'); if (p) p.pause(); document.getElementById('upPlay').textContent = '▶ play the take over the piano'; }
  document.getElementById('upPlay').addEventListener('click', () => {
    if (!take) return; const p = document.getElementById('piano'); if (timers.length) { stopUp(); return; }
    if (typeof pause === 'function') pause(); ac = ac || new (window.AudioContext || window.webkitAudioContext)(); if (ac.state === 'suspended') ac.resume();
    const t0 = Math.max(0, take.notes[0].t - 4), base = performance.now();
    if (p) { p.currentTime = Math.max(0, t0 - START); p.play(); }
    take.notes.forEach(n => timers.push(setTimeout(() => { const o = ac.createOscillator(), g = ac.createGain(), now = ac.currentTime, d = Math.max(0.08, n.end - n.t);
      o.type = 'triangle'; o.frequency.value = 440 * Math.pow(2, (n.pitch - 69) / 12); g.gain.setValueAtTime(0.0001, now); g.gain.exponentialRampToValueAtTime(0.22, now + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, now + d);
      o.connect(g).connect(ac.destination); o.start(now); o.stop(now + d + 0.05); }, (n.t - t0) * 1000)));
    timers.push(setTimeout(stopUp, (take.notes[take.notes.length - 1].end - t0 + 1.5) * 1000));
    document.getElementById('upPlay').textContent = '■ stop';
  });
})();
</script>"""


def body_parts(page):
    """The score block and the lines/log block of a canvas page, as HTML strings."""
    i = page.index(SCORE_START); j = page.index(COLS_START, i); k = page.rindex(SCRIPT_START)
    score = page[i:j]; cols = page[j:k]
    cols = cols[:cols.rindex("</div>")]   # drop the closing tag of #app
    return score, cols


def mix_src(page):
    return re.search(r'<audio id="mix" preload="auto" src="([^"]*)"', page).group(1)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("main"); ap.add_argument("--version", action="append", default=[], help="label=path/to/canvas/index.html")
    ap.add_argument("--main-label", default="Current"); ap.add_argument("--piano", help="the piano recording alone, for the voice checkbox")
    ap.add_argument("--artifact", action="store_true", help="inline the piano audio (claude.ai pages)"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--beat-offset", type=float, default=0.0, help="the canvas's notation offset, in the composer's beats")
    ap.add_argument("--upload", action="store_true", help="add a 'Load a take' button that engraves a take in the browser and plays it as a tone (no words, no singing)")
    a = ap.parse_args()
    page = Path(a.main).read_text()
    score0, cols0 = body_parts(page)
    vers = [(lab, *body_parts(Path(p).read_text()), mix_src(Path(p).read_text())) for lab, p in (v.split("=", 1) for v in a.version)]
    # rename the ids inside each extra version so nothing collides with the main one
    blocks = [f'<section class="ver" data-v="0">{score0}{cols0}</section>']
    for k, (lab, sc, co, _) in enumerate(vers, 1):
        sc = sc.replace(' id="score"', f' id="score-v{k}"', 1)
        blocks.append(f'<section class="ver" data-v="{k}" hidden>{sc}{co}</section>')
    ver_audio = "".join(f'<audio id="ver-{k}" preload="none" src="{src}"></audio>' for k, (_, _, _, src) in enumerate(vers, 1))
    piano_audio = ""
    if a.piano:
        psrc = ("data:audio/mpeg;base64," + base64.b64encode(Path(a.piano).read_bytes()).decode()) if a.artifact else Path(a.piano).name
        piano_audio = f'<audio id="piano" preload="none" src="{psrc}"></audio>'
    vpills = ""
    if vers:
        vpills = ('<div class="pills vpills" role="group" aria-label="version"><span class="mute" style="align-self:center">Version:</span>'
                  + f'<button class="vpill pill on" data-v="0">{a.main_label}</button>'
                  + "".join(f'<button class="vpill pill" data-v="{k}">{lab}</button>' for k, (lab, *_rest) in enumerate(vers, 1)) + '</div>')
    # splice: version pills above the voice pills, sections in place of the single score + cols
    i = page.index(SCORE_START); k = page.rindex(SCRIPT_START)
    tail = page[k:]
    head = page[:i]
    head = head.replace('<div class="pills" role="group" aria-label="voice">', vpills + '<div class="pills" role="group" aria-label="voice" id="voicepills">', 1) if '<div class="pills" role="group" aria-label="voice">' in head \
        else head.replace('<audio id="mix"', vpills + '<audio id="mix"', 1)
    upload = ('<div class="bar"><label class="pill" style="display:inline-block">Load a take (.json)<input type="file" id="takeFile" accept=".json,application/json" hidden></label>'
              '<span id="takeMsg" class="mute">A take saved from Play the Line: shown and played as a tone over the piano. Send it to the agent to have it fitted with words and sung.</span></div>')
    head = head.replace('<audio id="mix"', (upload if a.upload else "") + ver_audio + piano_audio + '<audio id="mix"', 1)
    script = """<script>
(function(){
  const vp = document.getElementById('voicepills'); let mainMix = null;
  function swapTo(el){ if (!el || el === mix) return; const t = mix.currentTime, playing = !mix.paused; mix.pause(); mix = el;
    const go = () => { mix.currentTime = t; if (playing) mix.play(); }; if (mix.readyState >= 1) go(); else { mix.addEventListener('loadedmetadata', go, {once: true}); mix.load(); } }
  document.querySelectorAll('.vpill').forEach(b => b.addEventListener('click', () => {
    const v = b.dataset.v; document.querySelectorAll('section.ver').forEach(s => s.hidden = s.dataset.v !== v);
    document.querySelectorAll('.vpill').forEach(x => x.classList.toggle('on', x === b));
    if (vp) vp.style.display = v === '0' ? '' : 'none';
    if (v === '0') { swapTo(mainMix || document.getElementById('mix')); } else { if (!mainMix || mix.id.startsWith('mix')) mainMix = mix; swapTo(document.getElementById('ver-' + v)); }
    const vo = document.getElementById('voiceOn'); if (vo) vo.checked = true; }));
  const vo = document.getElementById('voiceOn'), piano = document.getElementById('piano'); let sung = null;
  if (vo && piano) vo.addEventListener('change', () => { if (!vo.checked) { sung = mix; swapTo(piano); } else if (sung) { swapTo(sung); sung = null; } });
})();
</script>"""
    if a.upload:
        blocks.append('<section class="ver" data-v="up" hidden><div class="score" id="score-up"></div><div class="bar"><button id="upPlay">▶ play the take over the piano</button><span id="upClock" class="mute"></span></div><h2>Notes, by line</h2><ol id="upLines"></ol></section>')
    out = head + "\n".join(blocks) + "</div>\n" + tail.replace("</script>", "</script>" + script + (UPLOAD_JS.replace("__OFFSET__", str(a.beat_offset)) if a.upload else ""), 1)
    Path(a.out).write_text(out)
    print(f"wrote {a.out}: {1 + len(vers)} versions" + (", voice checkbox wired to the piano" if a.piano else ""))


if __name__ == "__main__":
    main()
