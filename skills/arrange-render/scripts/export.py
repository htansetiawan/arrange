#!/usr/bin/env python3
"""export.py — the Logic Pro handoff: numbered zero-aligned stems, tempo/marker MIDI, import notes.

    python3 export.py arrangement.json piano-analysis.json --spine piano.wav -o export/logic [--preroll-bars 1]

Every layer in `order` leaves as exactly one stem, or the export refuses and
names the layer: a generated layer needs a chosen rendered candidate, a take
needs its file, a stub is written as silence. All stems are 24-bit PCM at the
export rate, the recording's exact length plus the pre-roll padding that
tempo-markers.mid declares (see smf.py: DAW bar 1 is a pre-roll bar at the
first measured tempo, the performance's first downbeat starts DAW bar 2).
The MIDI carries the tempo map, time signature, section markers, the
transcribed piano and the vocal score, all on the same grid. IMPORT.md says
what to do and what to check in Logic; the check itself is the creator's.
"""
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
import smf  # noqa: E402
import arrangement as A  # noqa: E402
from clock import Clock, ClockError  # noqa: E402


def decode(path, sr, tmpdir):
    out = Path(tmpdir) / (Path(path).stem + ".decoded.wav")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-ar", str(sr), "-ac", "2", "-c:a", "pcm_f32le", str(out)], check=True)
    y, _ = sf.read(out, dtype="float32", always_2d=True)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arrangement"); ap.add_argument("analysis"); ap.add_argument("--spine", required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--preroll-bars", type=int, default=1); ap.add_argument("--midi", help="transcribed piano MIDI to include")
    a = ap.parse_args()
    plan, an = A.load(a.arrangement), A.load(a.analysis)
    problems = A.validate(plan, an)
    if problems:
        sys.exit("REFUSED: the plan is not valid: " + "; ".join(problems))
    sr = int(plan.get("export", {}).get("sr", 48000))
    piano, psr = sf.read(a.spine, dtype="float32", always_2d=True)
    if psr != sr:
        sys.exit(f"REFUSED: the recording is {psr} Hz and the export asks for {sr} Hz; resampling the spine is not done silently")
    n = len(piano)
    org = smf.origin(an, a.preroll_bars)
    pad = int(round(org["pad_s"] * sr)); total = n + pad
    # parity first: every layer must have a source before anything is written
    sources, missing = [], []
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid)
        if L["kind"] == "stub":
            sources.append((L, "stub", None)); continue
        if L["kind"] == "take":
            p = L.get("asset_path") or L.get("asset")
            if not p or not Path(str(p)).exists():
                missing.append(f"{lid} ({L['name']}): take file {p!r} not found"); continue
            sources.append((L, "take", p)); continue
        cand = next((c for c in L.get("candidates", []) if c["id"] == L.get("chosen") and c.get("status") == "rendered" and c.get("path")), None)
        if not cand:
            missing.append(f"{lid} ({L['name']}): no chosen rendered candidate (status {L.get('status')}{', stale' if L.get('stale') else ''})"); continue
        if L.get("stale"):
            missing.append(f"{lid} ({L['name']}): chosen candidate is stale ({L.get('stale_reason')})"); continue
        sources.append((L, "generated", cand["path"]))
    if missing:
        sys.exit("REFUSED: not every layer has a stem:\n  " + "\n  ".join(missing))
    out = Path(a.out); stems = out / "stems"; stems.mkdir(parents=True, exist_ok=True)
    report = {"export": "logic", "sr": sr, "bit_depth": 24, "recording_frames": n, "pad_frames": pad, "stem_frames": total, "origin": org, "stems": [], "logic_import": "awaiting the creator's check in Logic"}
    with tempfile.TemporaryDirectory(prefix="arrange-export-") as tmp:
        def write(name, audio):
            y = np.zeros((total, 2), dtype=np.float32); y[pad:pad + len(audio)] = audio[:n]
            p = stems / name; sf.write(p, y, sr, subtype="PCM_24")
            with sf.SoundFile(p) as f:
                ok = f.frames == total and f.samplerate == sr and f.channels == 2
            report["stems"].append({"file": name, "frames": total, "frames_ok": ok, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()[:16], "peak": round(float(np.abs(y).max()), 4)})
            return ok
        write("00_piano.wav", piano)
        for k, (L, kind, src) in enumerate(sources, 1):
            name = f"{k:02d}_{L['name'].replace(' ', '-')}" + ("_STUB" if kind == "stub" else "") + ".wav"
            if kind == "stub":
                write(name, np.zeros((n, 2), dtype=np.float32)); report["stems"][-1]["reason"] = L.get("stub_reason")
            else:
                write(name, decode(src, sr, tmp)); report["stems"][-1]["from"] = str(src); report["stems"][-1]["candidate"] = L.get("chosen")
    # MIDI: tempo map + markers + piano transcription + vocal score, all in the performance's bar:beat
    clk = Clock(an); specs = []; dropped = 0
    if a.midi:
        import pretty_midi
        pm = pretty_midi.PrettyMIDI(a.midi); notes = []
        for inst in pm.instruments:
            for nn in inst.notes:
                try:
                    b1, bt1 = clk.at(nn.start); b2, bt2 = clk.at(min(nn.end, clk.end()[0] - 1e-3))
                    dur = clk._ordinal(b2, bt2) - clk._ordinal(b1, bt1)
                    notes.append({"bar": b1, "beat": bt1, "dur_beats": max(0.05, dur), "pitch": nn.pitch, "vel": max(1, nn.velocity)})
                except ClockError:
                    dropped += 1
        specs.append({"name": "piano (transcribed)", "program": 0, "notes": notes})
    for lid in plan["order"]:
        L = A.layer_by_id(plan, lid)
        sc = Path(a.arrangement).parent / "jobs" / lid / "score.json"
        if L["route"] == "score" and sc.exists():
            rows = json.load(open(sc))["rows"]; notes = []
            for r in rows:
                if r["kind"] == "unsung":
                    continue
                try:
                    b1, bt1 = clk.at(r["t"]); b2, bt2 = clk.at(r["end"])
                    notes.append({"bar": b1, "beat": bt1, "dur_beats": max(0.05, clk._ordinal(b2, bt2) - clk._ordinal(b1, bt1)), "pitch": r["pitch"], "vel": 90})
                except ClockError:
                    dropped += 1
            specs.append({"name": f"{L['name']} score ({lid})", "program": 52, "notes": notes})
    org2 = smf.write(an, out / "tempo-markers.mid", specs, a.preroll_bars)
    report["midi"] = {"tracks": 1 + len(specs), "notes_dropped_outside_map": dropped, "beats": len(an["tempo_map"]["beats"]), "markers": len(an.get("sections", []))}
    for src in (a.arrangement, a.analysis):
        shutil.copy(src, out / Path(src).name)
    (out / "render-report.json").write_text(json.dumps(report, indent=1))
    first_bar = an["tempo_map"]["beats"][0]["bar"]
    (out / "IMPORT.md").write_text(f"""# Import into Logic Pro

1. New empty project at {sr} Hz. Turn Flex & Follow OFF for imported audio (Project Settings > Smart Tempo, or per region), so Logic never stretches the stems.
2. File > Import > MIDI File > `tempo-markers.mid`. Say YES when Logic asks to import the tempo. The tempo track then follows the performance beat by beat.
3. Select every file in `stems/`, drag them onto the tracks area at bar 1 beat 1, choose "Create new tracks", one per file.

How the grid lines up: DAW bar 1 is a pre-roll of {org2['preroll_bars']} bar(s) at the first measured tempo ({org2['preroll_s']:.3f} s).
The performance's bar {first_bar} starts at DAW bar {org2['daw_bar_of_first_downbeat']}. Every stem starts with {org2['pad_s']:.3f} s of silence so that
the recording's first sample sits {org2['lead_s']:.3f} s before that downbeat, exactly as recorded. Recording time = DAW time - {org2['pad_s']:.3f} s.

Stems: {", ".join(s['file'] for s in report['stems'])}. Files ending in _STUB are silent placeholders for undecided layers.

What to check and write down (this export is unverified until you do):
- Logic version; whether the tempo import was offered and accepted; the first marker's bar; the first downbeat of the piano against the bar line at DAW bar {org2['daw_bar_of_first_downbeat']};
- that the voice and the strings sit where the plan says (bars {', '.join(f"{A.layer_by_id(plan, l)['anchors']['enter']['bar']}-{A.layer_by_id(plan, l)['anchors']['exit']['bar']} {A.layer_by_id(plan, l)['name']}" for l in plan['order'])}, in the performance's numbering);
- Flex setting of the imported regions, and whether anything was stretched.
""")
    print(f"wrote {out}: {len(report['stems'])} stems of {total} frames ({'all exact' if all(s['frames_ok'] for s in report['stems']) else 'FRAME MISMATCH'}), MIDI with {report['midi']['tracks']} tracks ({dropped} notes outside the map dropped), IMPORT.md; pre-roll {org2['preroll_s']:.3f}s, pad {org2['pad_s']:.3f}s")


if __name__ == "__main__":
    main()
