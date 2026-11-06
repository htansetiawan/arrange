#!/usr/bin/env python3
"""make_voice.py — turn a song recording (a file or a video link) into a singing voice for /arrange-lyrics (plain python).

    python make_voice.py myvoice --source my_singing.m4a --consent "<name>, own voice; <allowed use>"
    python make_voice.py ref --source reference.wav --consent "none; private listening only" --private
    python make_voice.py myvoice --project arrange-project.json --shift -12      # rank clips for this song's line

One command for six steps:
  1. fetch the audio (a local m4a/mp3/wav, or a link via yt-dlp; use only recordings you have
     the right to use) into voices/<name>/source.wav
  2. write CONSENT.txt from --consent (required; --private marks it never-public)
  3. SoulX preprocessing: separate the voice from the band, find the sung notes and words (pre/)
  4. rank every 8-15 s stretch between breaths with pick_prompt.py (clean, sung, steady, in range)
  5. the best stretch becomes the voice (prompt.wav -> pre/vocal.wav, prompt.json); the next
     ones become <name>-clip2, <name>-clip3, so they can be heard side by side
  6. print what it found: the words it heard (a garbled transcript means a poor reference),
     the range, and the clips
Then: python sing.py arrange-project.json --voice <name> --shift <n> --n-steps 64 --try

A voice without consent is never used on a public page or in a paper; sing.py refuses a
voice folder without CONSENT.txt. Steps already done are skipped (delete pre/ to redo).
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def note(m):
    return f"{NAMES[int(m) % 12]}{int(m) // 12 - 1}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name"); ap.add_argument("--source", help="audio file or video link; omit to reuse the folder's source.wav")
    ap.add_argument("--consent", help="who agreed, and for what use (written to CONSENT.txt)"); ap.add_argument("--private", action="store_true", help="never public: no consent from the singer")
    ap.add_argument("--language", default="English", choices=["English", "Mandarin", "Cantonese"])
    ap.add_argument("--project", help="arrange-project.json: rank clips against this song's sung line"); ap.add_argument("--shift", type=int, default=0, help="the octave shift the voice will sing at (-12 = an octave down)")
    ap.add_argument("--target-median", type=float, help="median MIDI note the voice will sing (instead of --project)")
    ap.add_argument("--clips", type=int, default=3)
    a = ap.parse_args()
    cfg = arrange_config.load(); vd = Path(arrange_config.require(cfg, "voices_dir")) / a.name; vd.mkdir(parents=True, exist_ok=True)
    py_sx, py_an = cfg["python"]["soulx"], cfg["python"]["analysis"]

    # 1. audio
    wav = vd / "source.wav"
    if a.source:
        if a.source.startswith(("http://", "https://")):
            ytdlp = cfg.get("ytdlp") or shutil.which("yt-dlp")
            if not ytdlp:
                sys.exit("needs yt-dlp for a link: set \"ytdlp\" in the ARRANGE config or ARRANGE_YTDLP")
            subprocess.run([ytdlp, "--no-warnings", "-q", "-f", "bestaudio", "-x", "--audio-format", "wav", "-o", str(vd / "download.%(ext)s"), a.source], check=True)
            src = vd / "download.wav"
        else:
            src = Path(a.source).expanduser()
            shutil.copy(src, vd / ("original" + src.suffix))
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(src), "-map", "0:a:0", "-ac", "1", "-ar", "44100", str(wav)], check=True)
        (vd / "source.json").write_text(json.dumps({"source": a.source}, indent=1))
    if not wav.exists():
        sys.exit(f"no audio: give --source (file or link); {wav} does not exist")

    # 2. consent
    if a.consent:
        (vd / "CONSENT.txt").write_text(f"Voice: {a.name}, from {a.source or 'source.wav'}.\nConsent: {a.consent}\n"
                                        + ("Private listening only; never on a public page or in a paper.\n" if a.private else ""))
    if not (vd / "CONSENT.txt").exists():
        sys.exit("say who agreed and for what use: --consent \"...\" (add --private when the singer has not agreed)")

    # 3. separate and transcribe
    pre = vd / "pre"
    if not (pre / "metadata.json").exists():
        print("separating the voice and transcribing it (about two minutes for a four-minute song)...", flush=True)
        r = subprocess.run([py_sx, "-m", "preprocess.pipeline", "--audio_path", str(wav), "--save_dir", str(pre), "--language", a.language,
                            "--device", arrange_config.get(cfg, "device", "cuda"), "--vocal_sep", "True", "--midi_transcribe", "True"], cwd=arrange_config.require(cfg, "soulx.repo"), capture_output=True, text=True)
        (vd / "pre.log").write_text(r.stdout[-6000:] + "\n--- stderr ---\n" + r.stderr[-6000:])
        if r.returncode or not (pre / "metadata.json").exists():
            sys.exit(f"preprocessing failed; see {vd / 'pre.log'}")
    meta = json.load(open(pre / "metadata.json"))
    allp = [int(x) for s in meta for x in s["note_pitch"].split() if int(x) > 0]
    print(f"heard {len(meta)} sung stretches, range {note(min(allp))}-{note(max(allp))}")
    for s in meta[:4]:
        print(f"  {s['time'][0] / 1000:6.1f} s  {s['text'].replace('<SP>', '/')[:100]}")

    # 4-5. rank the clips and make the voice
    if a.target_median is not None:
        target = a.target_median
    elif a.project:
        proj, _ = arrange_config.project(a.project)
        rows = [r for r in json.load(open(proj["fit"]))["rows"] if r["kind"] == "note"]
        target = sorted(r["pitch"] for r in rows)[len(rows) // 2] + a.shift
    else:
        target = sorted(allp)[len(allp) // 2]   # the singer's own middle
    r = subprocess.run([py_an, str(HERE / "pick_prompt.py"), str(vd), "--target-median", str(target), "--top", str(a.clips), "--write"], capture_output=True, text=True)
    print(r.stdout, end="")
    if r.returncode or not (vd / "prompt.json").exists():
        sys.exit("no usable clip found: " + r.stderr[-400:])
    for link in [vd / "prompt.wav"]:
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to("pre/vocal.wav")
    made = [a.name]
    for k in range(2, a.clips + 1):
        pj = vd / f"prompt-{k}.json"
        if not pj.exists():
            continue
        cd = vd.parent / f"{a.name}-clip{k}"; cd.mkdir(exist_ok=True)
        shutil.copy(pj, cd / "prompt.json"); shutil.copy(vd / "CONSENT.txt", cd / "CONSENT.txt")
        if (cd / "prompt.wav").exists() or (cd / "prompt.wav").is_symlink():
            (cd / "prompt.wav").unlink()
        (cd / "prompt.wav").symlink_to(Path("..") / a.name / "pre" / "vocal.wav")
        made.append(cd.name)
    print("VOICES:", " ".join(made))
    print(f"next: sing.py <project> --voice {a.name} --shift {a.shift} --n-steps 64 --try   (and the -clip voices, to compare)")


if __name__ == "__main__":
    main()
