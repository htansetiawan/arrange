#!/usr/bin/env python3
"""analyze.py — /arrange-listen in one shot (analysis python: librosa, pretty_midi, soundfile).

    python analyze.py piano.wav --midi piano.mid -o analysis/ [--time-sig 4/4] [--bpm 52] [--sections "theme 1:17-32,..."]
                      [--theme-at 46.75 --theme-at 73.93] [--click click.mp3] [--confirmed]

Facts with provenance, no arranging. Stages: probe (sr, channels, length,
leading and trailing silence, sha256), transcription (an existing Kong MIDI is
taken as given and counted), tempo map (beat tracking on an onset envelope
built from the transcription, bass-weighted downbeat phase, rubato level,
confidence, unresolved bars), key (Krumhansl profiles on duration-weighted
pitch classes), sections (a proposal: eight-bar phrases, plus theme
statements where given), melody (skyline per onset cluster, bar:beat
positions), dynamics (per-bar RMS). Writes piano-analysis.json plus
melody.json, melody.mid, and optionally a click track MP3 so the creator can
confirm or correct the beats. A map the creator confirmed (--confirmed) is
marked creator-confirmed and must not be overwritten by a re-run.
"""
import argparse, hashlib, json, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf
import librosa

KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    y, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = y.mean(axis=1)
    win = int(sr * 0.01)
    rms = np.sqrt(np.convolve(mono ** 2, np.ones(win) / win, mode="same") + 1e-12)
    thr = 10 ** (-60 / 20)
    loud = np.where(rms > thr)[0]
    lead = float(loud[0] / sr) if len(loud) else 0.0
    tail = float((len(mono) - loud[-1]) / sr) if len(loud) else 0.0
    peak = float(np.abs(y).max())
    return {"path": str(path), "sha256": sha256(path), "sr": sr, "channels": y.shape[1], "dur_s": round(len(mono) / sr, 3),
            "frames": int(len(mono)), "peak_dbfs": round(20 * np.log10(peak + 1e-12), 2),
            "silence_lead_s": round(lead, 3), "silence_tail_s": round(tail, 3)}, mono, sr


def onset_envelope(notes, dur, sr=22050, hop=512, bass_weight=1.0):
    n = int(dur * sr / hop) + 2
    env = np.zeros(n)
    bass = np.zeros(n)
    for st, pitch, vel in notes:
        i = int(round(st * sr / hop))
        if 0 <= i < n:
            env[i] += vel / 127.0
            if pitch <= 55:
                bass[i] += vel / 127.0
    k = np.array([0.25, 0.5, 1.0, 0.5, 0.25])
    env = np.convolve(env + bass_weight * bass, k, mode="same")
    return env, bass, sr, hop


def tempo_map(notes, dur, time_sig="4/4", bpm=None, tightness=100):
    env, bass, sr, hop = onset_envelope(notes, dur)
    bpb = int(time_sig.split("/")[0])
    start_bpm = bpm or 60.0
    t_est, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop, start_bpm=start_bpm, tightness=tightness, units="frames", trim=False)
    beat_t = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
    # snap each beat to the nearest onset within 120 ms, if any (the transcription is the evidence)
    onsets = np.array(sorted(set(round(s, 3) for s, _, _ in notes)))
    snapped, support = [], []
    for t in beat_t:
        j = np.searchsorted(onsets, t)
        cands = [onsets[k] for k in (j - 1, j) if 0 <= k < len(onsets)]
        near = min(cands, key=lambda o: abs(o - t)) if cands else None
        if near is not None and abs(near - t) <= 0.12:
            snapped.append(float(near)); support.append(1.0 - abs(near - t) / 0.12)
        else:
            snapped.append(float(t)); support.append(0.0)
    snapped = np.array(snapped)
    # downbeat phase: where the bass lands most
    bass_t = np.array(sorted(set(round(s, 3) for s, p, _ in notes if p <= 55)))
    def bass_hits(idx):
        tot = 0.0
        for t in snapped[idx]:
            j = np.searchsorted(bass_t, t)
            for k in (j - 1, j):
                if 0 <= k < len(bass_t) and abs(bass_t[k] - t) <= 0.1:
                    tot += 1; break
        return tot
    scores = [bass_hits(np.arange(p, len(snapped), bpb)) for p in range(bpb)]
    phase = int(np.argmax(scores))
    beats = []
    for i, t in enumerate(snapped):
        k = i - phase
        bar = 1 + k // bpb if k >= 0 else 0
        beat = (k % bpb) + 1
        beats.append({"t": round(float(t), 3), "bar": int(bar), "beat": int(beat)})
    durs = np.diff(snapped)
    med = float(np.median(durs))
    cv = float(np.std(durs) / np.mean(durs))
    rubato = "low" if cv < 0.08 else "medium" if cv < 0.18 else "high"
    unresolved, weak = [], [b["bar"] for b, s in zip(beats, support) if s == 0.0]
    if weak:
        runs, start, prev = [], weak[0], weak[0]
        for b in weak[1:] + [None]:
            if b != prev and b != (prev + 1 if prev is not None else None):
                runs.append((start, prev)); start = b
            prev = b
        for a, b in runs:
            unresolved.append(f"bars {a}–{b}: no played note within 120 ms of a tracked beat; the beat is the tracker's guess there" if a != b else f"bar {a}: no played note within 120 ms of a tracked beat; the beat is the tracker's guess there")
    for i in np.where(durs > 2.0 * med)[0]:
        unresolved.append(f"bar {beats[i]['bar']}: a {durs[i]:.2f}s gap between beats {beats[i]['beat']} and the next (typical {med:.2f}s); fermata, pause or a missed beat")
    return {"method": "onsets(Kong)+librosa-beat, bass-weighted downbeat phase", "time_signature": time_sig,
            "beats": beats, "bpm_mean": round(60.0 / float(np.mean(durs)), 1), "bpm_min": round(60.0 / float(durs.max()), 1), "bpm_max": round(60.0 / float(durs.min()), 1),
            "rubato": rubato, "tempo_cv": round(cv, 3), "confidence": round(float(np.mean(support)), 2), "downbeat_phase_scores": scores,
            "tracker_start_bpm": start_bpm, "tracker_estimate_bpm": round(float(np.atleast_1d(t_est)[0]), 1),
            "inspection": "auto", "revision": 0, "unresolved": unresolved}


def key_of(pm_notes):
    pc = np.zeros(12)
    for st, en, pitch, vel in pm_notes:
        pc[pitch % 12] += (en - st) * vel / 127.0
    best = []
    for tonic in range(12):
        for mode, prof in (("major", KS_MAJOR), ("minor", KS_MINOR)):
            r = np.corrcoef(np.roll(prof, tonic), pc)[0, 1]
            best.append((r, tonic, mode))
    best.sort(reverse=True)
    r, tonic, mode = best[0]
    return {"tonic": NAMES[tonic], "mode": mode, "confidence": round(float(r), 2), "runner_up": f"{NAMES[best[1][1]]} {best[1][2]} ({best[1][0]:.2f})", "modulations": []}


def sections_proposal(beats, theme_at, overrides):
    last_bar = beats[-1]["bar"]
    if overrides:
        out = []
        for i, item in enumerate(overrides.split(",")):
            label, rng = item.split(":"); a, b = (int(x) for x in rng.split("-"))
            out.append({"id": f"s{i+1}", "label": label.strip(), "bar_start": a, "bar_end": b, "source": "creator"})
        return out
    downbeats = {b["bar"]: b["t"] for b in beats if b["beat"] == 1}
    marks = {}
    for k, t in enumerate(theme_at, 1):
        bar = min(downbeats, key=lambda b: abs(downbeats[b] - t)) if downbeats else 1
        marks[bar] = f"theme {k}"
    bounds = sorted(set([1] + list(marks) + [last_bar + 1]))
    out, i = [], 0
    for a, b in zip(bounds, bounds[1:]):
        start = a
        while start < b:
            end = min(start + 7, b - 1)
            i += 1
            label = marks.get(start, f"phrase {i}") if start == a else f"phrase {i}"
            out.append({"id": f"s{i}", "label": label, "bar_start": start, "bar_end": end, "source": "auto"})
            start = end + 1
    return out


def skyline(pm_notes, beats):
    """Highest note per onset cluster (50 ms); positions in bar:beat from the map; durations to the next skyline onset."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
    from clock import Clock, ClockError
    clk = Clock({"tempo_map": {"beats": beats, "time_signature": "4/4"}})
    notes = sorted(pm_notes)
    clusters, cur = [], []
    for n in notes:
        if cur and n[0] - cur[0][0] > 0.05:
            clusters.append(cur); cur = []
        cur.append(n)
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        top = max(c, key=lambda n: n[2])
        try:
            bar, beat = clk.at(top[0])
        except ClockError:
            continue
        out.append({"t": round(top[0], 3), "end": round(top[1], 3), "pitch": top[2], "vel": top[3], "bar": bar, "beat": round(beat, 3)})
    for a, b in zip(out, out[1:]):
        a["end"] = min(a["end"], b["t"]) if b["t"] > a["t"] else a["end"]
    return out


def dynamics(mono, sr, beats):
    out = []
    downbeats = [b for b in beats if b["beat"] == 1]
    for d1, d2 in zip(downbeats, downbeats[1:]):
        seg = mono[int(d1["t"] * sr):int(d2["t"] * sr)]
        if len(seg):
            out.append({"bar": d1["bar"], "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)), 1)})
    return out


def click_track(src_path, beats, out_mp3, start=None, end=None):
    y, sr = sf.read(src_path, dtype="float32", always_2d=True)
    y = y * 0.5
    for b in beats:
        f0, amp, length = (1500.0, 0.6, 0.04) if b["beat"] == 1 else (1000.0, 0.35, 0.025)
        i = int(b["t"] * sr); n = int(length * sr)
        if i + n < len(y):
            tt = np.arange(n) / sr
            blip = (amp * np.sin(2 * np.pi * f0 * tt) * np.exp(-tt * 60)).astype(np.float32)
            y[i:i + n] += blip[:, None]
    if start is not None:
        y = y[int(start * sr):int((end or len(y) / sr) * sr)]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, np.clip(y, -1, 1), sr)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", tmp.name, "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)], check=True)
    Path(tmp.name).unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("--midi", required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--time-sig", default="4/4"); ap.add_argument("--bpm", type=float); ap.add_argument("--tightness", type=float, default=100)
    ap.add_argument("--sections"); ap.add_argument("--theme-at", type=float, action="append", default=[])
    ap.add_argument("--click"); ap.add_argument("--click-window", type=float, nargs=2)
    ap.add_argument("--confirmed", action="store_true", help="the creator listened and confirmed this map")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    source, mono, sr = probe(a.audio)
    pm = pretty_midi.PrettyMIDI(a.midi)
    pm_notes = sorted((float(n.start), float(n.end), int(n.pitch), int(n.velocity)) for i in pm.instruments for n in i.notes)
    pedal = sum(1 for i in pm.instruments for c in i.control_changes if c.number == 64)
    tm = tempo_map([(s, p, v) for s, e, p, v in pm_notes], source["dur_s"], a.time_sig, a.bpm, a.tightness)
    if a.confirmed:
        tm["method"] = "creator-confirmed (" + tm["method"] + ")"; tm["inspection"] = "creator-confirmed"
    key = key_of(pm_notes)
    secs = sections_proposal(tm["beats"], a.theme_at, a.sections)
    mel = skyline(pm_notes, tm["beats"])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "arrange-plan/scripts"))
    from clock import Clock
    clk = Clock({"tempo_map": tm})
    for s in secs:
        s["t0"] = round(clk.t(s["bar_start"], 1)[0], 3)
        try:
            s["t1"] = round(clk.bar_end(s["bar_end"])[0], 3)
        except Exception:
            s["t1"] = round(clk.end()[0], 3)
    nps = {s["id"]: sum(1 for m in mel if s["bar_start"] <= m["bar"] <= s["bar_end"]) for s in secs}
    mpm = pretty_midi.PrettyMIDI(); inst = pretty_midi.Instrument(0, name="melody (skyline)")
    for m in mel:
        inst.notes.append(pretty_midi.Note(velocity=m["vel"], pitch=m["pitch"], start=m["t"], end=max(m["t"] + 0.05, m["end"])))
    mpm.instruments.append(inst); mpm.write(str(out / "melody.mid"))
    (out / "melody.json").write_text(json.dumps(mel, indent=1))
    pitches = [m["pitch"] for m in mel]
    analysis = {"schema": "arrange/piano-analysis@1", "source": source,
                "transcription": {"midi": str(Path(a.midi)), "tool": "bytedance piano_transcription_inference (Kong et al. 2021)", "notes": len(pm_notes), "pedal_events": pedal,
                                  "first_note_s": round(pm_notes[0][0], 3), "confidence": "high" if len(pm_notes) > 100 else "low", "inspection": "auto"},
                "tempo_map": tm, "key": key, "sections": secs,
                "melody": {"midi": str(out / "melody.mid"), "json": str(out / "melody.json"), "method": "skyline",
                           "range": {"low": pretty_midi.note_number_to_name(min(pitches)), "high": pretty_midi.note_number_to_name(max(pitches))},
                           "notes": len(mel), "notes_per_section": nps, "inspection": "auto"},
                "dynamics": dynamics(mono, sr, tm["beats"]),
                "derived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "unresolved": [f"time signature: {a.time_sig} {'given by the creator' if a.time_sig != '4/4' or a.bpm else 'assumed'}",
                               "melody: skyline (highest note per onset); inner-voice melodies would be missed"]}
    (out / "piano-analysis.json").write_text(json.dumps(analysis, indent=1, ensure_ascii=False))
    if a.click:
        w = a.click_window or (None, None)
        click_track(a.audio, tm["beats"], a.click, *w)
    print(f"{source['dur_s']}s, lead silence {source['silence_lead_s']}s, first note {analysis['transcription']['first_note_s']}s, {len(pm_notes)} notes, {pedal} pedal events")
    print(f"map: {len(tm['beats'])} beats, bars {tm['beats'][0]['bar']}:{tm['beats'][0]['beat']} to {tm['beats'][-1]['bar']}:{tm['beats'][-1]['beat']}, {tm['bpm_mean']} bpm mean ({tm['bpm_min']}–{tm['bpm_max']}), rubato {tm['rubato']} (cv {tm['tempo_cv']}), beat support {tm['confidence']}, tracker said {tm['tracker_estimate_bpm']} bpm, downbeat phase scores {tm['downbeat_phase_scores']}")
    print(f"key: {key['tonic']} {key['mode']} ({key['confidence']}; runner-up {key['runner_up']})")
    print("sections: " + "; ".join(f"{s['label']} bars {s['bar_start']}–{s['bar_end']} ({s['t0']}s)" for s in secs))
    print(f"melody: {len(mel)} skyline notes, {analysis['melody']['range']['low']}–{analysis['melody']['range']['high']}")
    for u in tm["unresolved"]:
        print("UNRESOLVED:", u)


if __name__ == "__main__":
    main()
