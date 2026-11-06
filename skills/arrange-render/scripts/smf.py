#!/usr/bin/env python3
"""smf.py — write tempo-markers.mid for the Logic Pro target. Stdlib only.

    python3 smf.py piano-analysis.json -o tempo-markers.mid [--notes notes.json ...] [--preroll-bars 1]

Track 0: a pre-roll, then the tempo map (one tempo event per measured beat so
Logic's grid follows the rubato), the time signature, and one marker per
section. Tracks 1..n: optional note tracks from JSON files of the form
  {"name": "piano", "program": 0, "notes": [{"bar": 9, "beat": 1.0, "dur_beats": 1.0, "pitch": 60, "vel": 80}, ...]}
with positions in the performance's own bar:beat.

The origin problem: the first measured downbeat sits some way into the
recording (0.42 s in the example); a writer that put it at tick 0 would land
every beat 0.42 s early against zero-aligned stems. This writer fixes the
origin explicitly:

- DAW tick 0 is the start of a pre-roll of `preroll_bars` whole bars played
  at the first measured beat's tempo. The performance's first downbeat is at
  the end of the pre-roll.
- Stems exported for this file must be padded at the start with
  `pad_s = preroll_s - lead_s` seconds of silence (lead_s = time of the first
  beat in the recording). If the recording's lead is longer than the
  pre-roll, more pre-roll bars are added until it fits, so pad_s >= 0 and the
  original audio is never trimmed.
- write() returns the origin record {preroll_bars, preroll_s, lead_s, pad_s,
  daw_bar_of_first_downbeat}; export writes it into IMPORT.md and the report.
  recording_time = daw_time - pad_s.

Tempos outside Logic's range (5 to 990 bpm) and invalid note values are
refused, not clamped; a refusal is a map or score problem to fix upstream.
"""
import argparse, json, math, struct
from pathlib import Path

PPQ = 480
BPM_MIN, BPM_MAX = 5.0, 990.0


class SMFError(Exception):
    pass


def vlq(n: int) -> bytes:
    if n < 0 or n > 0x0FFFFFFF:
        raise SMFError(f"delta time {n} out of range")
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def track_chunk(events) -> bytes:
    """events: list of (abs_tick, bytes_without_delta). Returns an MTrk chunk."""
    events = sorted(events, key=lambda e: e[0])
    out, last = bytearray(), 0
    for tick, ev in events:
        if tick < last:
            raise SMFError("events are not in order")
        out += vlq(tick - last) + ev
        last = tick
    out += vlq(0) + b"\xff\x2f\x00"
    return b"MTrk" + struct.pack(">I", len(out)) + bytes(out)


def tempo_bytes(seconds_per_beat: float, den: int) -> bytes:
    us_per_q = seconds_per_beat * 1_000_000 * (den / 4)
    bpm = 60_000_000 / us_per_q
    if not (BPM_MIN <= bpm <= BPM_MAX):
        raise SMFError(f"a beat of {seconds_per_beat:.3f}s is {bpm:.1f} bpm, outside {BPM_MIN:g}-{BPM_MAX:g}")
    return b"\xff\x51\x03" + int(round(us_per_q)).to_bytes(3, "big")


def origin(analysis: dict, preroll_bars: int = 1):
    tm = analysis["tempo_map"]
    beats = sorted(tm["beats"], key=lambda b: b["t"])
    if len(beats) < 2:
        raise SMFError("tempo map needs at least two beats")
    num = int(tm.get("time_signature", "4/4").split("/")[0])
    lead_s = float(beats[0]["t"])
    first_beat_s = float(beats[1]["t"]) - lead_s
    if first_beat_s <= 0:
        raise SMFError("first two beats are not increasing in time")
    bars = max(1, int(preroll_bars))
    while bars * num * first_beat_s < lead_s:
        bars += 1
    preroll_s = bars * num * first_beat_s
    return {"preroll_bars": bars, "preroll_beats": bars * num, "preroll_s": preroll_s,
            "lead_s": lead_s, "pad_s": preroll_s - lead_s,
            "first_downbeat": {"bar": beats[0]["bar"], "beat": beats[0]["beat"]},
            "daw_bar_of_first_downbeat": bars + 1, "first_beat_s": first_beat_s}


def tempo_track(analysis: dict, preroll_bars: int = 1):
    tm = analysis["tempo_map"]
    beats = sorted(tm["beats"], key=lambda b: b["t"])
    num, den = (int(x) for x in tm.get("time_signature", "4/4").split("/"))
    if den not in (1, 2, 4, 8, 16):
        raise SMFError(f"unsupported denominator {den}")
    den_pow = {1: 0, 2: 1, 4: 2, 8: 3, 16: 4}[den]
    tpb = PPQ * 4 // den
    org = origin(analysis, preroll_bars)
    pre_ticks = org["preroll_beats"] * tpb
    ev = [(0, b"\xff\x58\x04" + bytes([num, den_pow, 24, 8])),
          (0, b"\xff\x03" + vlq(len(b"tempo map")) + b"tempo map"),
          (0, tempo_bytes(org["first_beat_s"], den)),
          (0, b"\xff\x06" + vlq(len(b"pre-roll")) + b"pre-roll")]
    for i, b in enumerate(beats):
        dur = (beats[i + 1]["t"] - b["t"]) if i + 1 < len(beats) else (b["t"] - beats[i - 1]["t"])
        ev.append((pre_ticks + i * tpb, tempo_bytes(dur, den)))
    first_bar, first_beat = beats[0]["bar"], beats[0]["beat"]

    def tick_of(bar, beat):
        return pre_ticks + int(round(((bar - first_bar) * num + (beat - first_beat)) * tpb))

    for s in analysis.get("sections", []):
        name = s["label"].encode("utf-8")
        ev.append((tick_of(s["bar_start"], 1), b"\xff\x06" + vlq(len(name)) + name))
    return track_chunk(ev), tick_of, org


def note_track(spec: dict, tick_of, tpb: int):
    name = spec.get("name", "track").encode("utf-8")
    program = int(spec.get("program", 0))
    if not 0 <= program <= 127:
        raise SMFError(f"program {program} out of range")
    ev = [(0, b"\xff\x03" + vlq(len(name)) + name), (0, bytes([0xC0, program]))]
    for n in spec.get("notes", []):
        p, v = int(n["pitch"]), int(n.get("vel", 80))
        if not 0 <= p <= 127 or not 1 <= v <= 127:
            raise SMFError(f"note pitch {p} / velocity {v} out of range")
        dur = float(n.get("dur_beats", 1.0))
        if not dur > 0:
            raise SMFError(f"note at bar {n['bar']}:{n['beat']} has no duration")
        start = tick_of(n["bar"], float(n["beat"]))
        end = start + max(1, int(round(dur * tpb)))
        ev.append((start, bytes([0x90, p, v])))
        ev.append((end, bytes([0x80, p, 0])))
    return track_chunk(ev)


def write(analysis: dict, out: Path, note_specs=(), preroll_bars: int = 1):
    """Write the file; return the origin record (preroll, lead, pad)."""
    t0, tick_of, org = tempo_track(analysis, preroll_bars)
    den = int(analysis["tempo_map"].get("time_signature", "4/4").split("/")[1])
    tpb = PPQ * 4 // den
    tracks = [t0] + [note_track(s, tick_of, tpb) for s in note_specs]
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    Path(out).write_bytes(header + b"".join(tracks))
    return org


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--notes", nargs="*", default=[])
    ap.add_argument("--preroll-bars", type=int, default=1)
    a = ap.parse_args()
    analysis = json.loads(Path(a.analysis).read_text())
    specs = [json.loads(Path(p).read_text()) for p in a.notes]
    try:
        org = write(analysis, Path(a.out), specs, a.preroll_bars)
    except SMFError as e:
        raise SystemExit(f"REFUSED: {e}")
    print(f"wrote {a.out}: tempo track + {len(specs)} note track(s), {len(analysis['tempo_map']['beats'])} tempo events, "
          f"{len(analysis.get('sections', []))} markers; pre-roll {org['preroll_bars']} bar(s) = {org['preroll_s']:.3f}s, "
          f"lead {org['lead_s']:.3f}s, pad stems by {org['pad_s']:.3f}s; first downbeat = DAW bar {org['daw_bar_of_first_downbeat']}")


if __name__ == "__main__":
    main()
