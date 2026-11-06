#!/usr/bin/env python3
"""transpose.py — move the whole song into another key so a voice sings where it is comfortable (/arrange-lyrics; plain python + ffmpeg).

    python transpose.py arrange-project.json --semitones -3            # a project copy in the new key
    python transpose.py arrange-project.json --for-voice NAME           # the older clip rule; prefer center.py's key

A borrowed voice copies a singer's colour, and a singer's colour lives in their own
range: asked to sing far above or below it, the copy stops sounding like them. An
octave shift keeps the song in key but moves 12 semitones at a time. This moves the
piano recording too (ffmpeg's rubberband pitch shifter, formants preserved, tempo
unchanged), so voice and piano stay together in the new key, and writes a project
copy whose voice sings the score shifted by the same amount.

--for-voice NAME with --semitones K --octave O applies the key the composer chose
(center.py proposes it: K is its piano key, O its octave). --for-voice alone
picks with the older clip rule: the reference clip's median note against the
line's (prompt-candidates.json), the octave and the smallest transposition (at
most 6 semitones either way) that put the line's middle on the clip's; that
rule tends to be too high (references/keys.md), so prefer center.py.
The copy is arrange-project.key<+n>[-NAME].json beside the original; the original
project is untouched.
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--semitones", type=int); ap.add_argument("--for-voice")
    ap.add_argument("--octave", type=int, help="with --semitones and --for-voice: the voice's octave shift (e.g. 0 or -12); default = the one --for-voice picks")
    a = ap.parse_args()
    cfg = arrange_config.load(); proj, base = arrange_config.project(a.project)
    raw = json.loads(Path(a.project).read_text())
    rows = [r for r in json.load(open(proj["fit"]))["rows"] if r.get("kind") == "note"]
    line_mid = sorted(r["pitch"] for r in rows)[len(rows) // 2]
    octave = 0
    if a.for_voice:
        vd = Path(arrange_config.require(cfg, "voices_dir")) / a.for_voice
        voice_mid = json.load(open(vd / "prompt-candidates.json"))[0]["median"]
        # best octave first, then the remaining distance as a transposition of at most 6 semitones
        octave = 12 * round((voice_mid - line_mid) / 12)
        semis = int(round(voice_mid - line_mid - octave))
        if abs(semis) > 6:
            semis -= 12 * (1 if semis > 0 else -1); octave += 12 * (1 if semis < 0 else -1)
        if a.semitones is not None:   # the composer's own key for this voice
            semis = a.semitones; octave = a.octave if a.octave is not None else octave
        print(f"{a.for_voice}: reference centre {voice_mid:.0f}, line centre {line_mid} -> octave {octave:+d}, key {semis:+d} semitones")
    else:
        semis = a.semitones or 0
    w0, w1 = proj.get("window", [0, 75])
    src = Path(proj["recording"]); out = base / "source" / f"recording-key{semis:+d}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        ratio = 2 ** (semis / 12)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-t", str(w1 + 5),
                        "-af", f"rubberband=pitch={ratio:.6f}:formant=preserved:pitchq=quality", "-ar", "44100", str(out)], check=True)
    raw["recording"] = str(out.relative_to(base)) if str(out).startswith(str(base)) else str(out)
    raw["transpose"] = semis
    if a.for_voice:
        raw["voice"] = a.for_voice; raw["voice_shift"] = octave + semis
    else:
        raw["voice_shift"] = int(raw.get("voice_shift", 0)) + semis
    raw["build"] = f"build/key{semis:+d}"; raw.pop("voice_mix", None); raw.pop("voices", None); raw.pop("versions", None)
    dst = Path(a.project).with_name(Path(a.project).stem + f".key{semis:+d}" + (f"-{a.for_voice}" if a.for_voice else "") + ".json")
    dst.write_text(json.dumps(raw, indent=1, ensure_ascii=False))
    print(f"TRANSPOSED: {semis:+d} semitones; piano -> {out.name}; voice shift {raw['voice_shift']:+d}; project -> {dst.name}")
    print(f"next: sing.py {dst.name} --n-steps 64 --try")


if __name__ == "__main__":
    main()
