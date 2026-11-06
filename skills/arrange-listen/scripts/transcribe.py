#!/usr/bin/env python3
"""transcribe.py — piano audio to MIDI with Kong et al.'s high-resolution transcription, onsets, offsets and pedal (/arrange-listen; analysis python).

    python transcribe.py takes/piano.wav -o analysis/piano.mid [--device cuda] [--checkpoint kong.pth]

Uses the open ByteDance package `piano_transcription_inference` (Kong, Li, Song,
Wan, Wang, IEEE/ACM TASLP 2021; checkpoint note F1 0.9677, pedal F1 0.9186).
Writes the MIDI and, beside it, <name>.json with the facts the rest of the chain
reads: notes, pedal events, pitch range, first note time, seconds taken, and
"inspection": "auto" (nobody has listened yet). Reliable on solo piano; a band,
voice or strings come back as piano notes too, so separate first when the
recording is not a solo.

The checkpoint is --checkpoint, else $ARRANGE_KONG_CHECKPOINT, else the package's default
(~/piano_transcription_inference_data/, downloaded with wget on first use; see docs/setup.md).
"""
import argparse, json, os, time
from pathlib import Path

import librosa
import pretty_midi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--device", default="auto", help="cuda, cpu, or auto (cuda when this environment has it)")
    ap.add_argument("--checkpoint", default=os.environ.get("ARRANGE_KONG_CHECKPOINT"), help="Kong's note+pedal .pth (default: $ARRANGE_KONG_CHECKPOINT, else the package's own path)")
    a = ap.parse_args()
    from piano_transcription_inference import PianoTranscription, sample_rate
    import torch
    if a.device == "auto":
        a.device = "cuda" if torch.cuda.is_available() else "cpu"
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    y, _ = librosa.load(a.audio, sr=sample_rate, mono=True)
    t0 = time.time()
    PianoTranscription(device=a.device, checkpoint_path=a.checkpoint).transcribe(y, str(out))
    took = time.time() - t0
    pm = pretty_midi.PrettyMIDI(str(out))
    notes = [n for inst in pm.instruments for n in inst.notes]
    pedal = [c for inst in pm.instruments for c in inst.control_changes if c.number == 64]
    facts = {"audio": str(Path(a.audio).resolve()), "midi": str(out.resolve()), "tool": "bytedance piano_transcription_inference (Kong et al. 2021)",
             "duration_s": round(len(y) / sample_rate, 2), "notes": len(notes), "pedal_events": len(pedal),
             "pitch_range": [min(n.pitch for n in notes), max(n.pitch for n in notes)] if notes else None,
             "first_note_s": round(min(n.start for n in notes), 3) if notes else None, "seconds_taken": round(took, 1), "inspection": "auto"}
    out.with_suffix(".json").write_text(json.dumps(facts, indent=1))
    print(f"TRANSCRIBED: {len(notes)} notes, {len(pedal)} pedal events in {took:.1f} s -> {out}")


if __name__ == "__main__":
    main()
