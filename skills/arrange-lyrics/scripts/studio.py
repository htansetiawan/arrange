#!/usr/bin/env python3
"""studio.py — build the two ARRANGE pages for a project: Play the Line and the Score Canvas (/arrange-lyrics; plain python).

    python studio.py arrange-project.json [--start-bar 17]

Play the Line: the composer plays the vocal line on keys over the recording,
taps their own beat grid, and saves takes to the page's store.
Score Canvas: the current fit engraved (bar numbers in the composer's count, notes, words,
note numbers, key-correct accidentals; chord names only if the project lists
them), click-to-play over the current sung mix, with the lines and the sounds
sent to the singer for each syllable below it.
Both are written as self-contained pages (audio embedded) to the project's
studio folder. They can be opened locally or hosted; hosted as claude.ai
artifacts, the recorder uses the db capability to save takes (see references/studio.md). Paths come from
the project file; tools from the ARRANGE config.
"""
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402


def cut_mp3(src, dst, start, dur, mono=False, kbps=128):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(start), "-t", str(dur), "-i", str(src)] + (["-ac", "1"] if mono else []) + ["-c:a", "libmp3lame", "-b:a", f"{kbps}k", str(dst)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--start-bar", type=int, default=1); ap.add_argument("--canvas-only", action="store_true")
    a = ap.parse_args()
    cfg = arrange_config.load(); proj, base = arrange_config.project(a.project)
    studio = Path(proj.get("studio", base / "studio")); studio.mkdir(parents=True, exist_ok=True)
    w0, w1 = proj.get("window", [0, 70])
    piano = studio / f"piano-{w0:g}s-{w1:g}s.mp3"; cut_mp3(proj["recording"], piano, w0, w1 - w0, mono=True, kbps=96)
    title = proj.get("title", "Untitled")
    # Play the Line: the measured map is the base grid; the composer's taps live in the page
    if not a.canvas_only:
      subprocess.run([cfg["python"]["plain"], str(HERE / "recorder.py"), "--analysis", proj["analysis_measured"], "--audio", str(piano), "--audio-start", str(w0),
                    "--duration", str(w1 - w0), "--start-bar", str(a.start_bar), "--title", f"{title} · Play the Line", "-o", str(studio / "play-the-line.html"), "--artifact"], check=True)
    # Score Canvas: the current fit on the composer's tapped map (or the measured one before any taps)
    mix = proj.get("voice_mix") or str(piano)
    ref_args = []
    if proj.get("reference"):
        ref = studio / "reference-voice.mp3"; cut_mp3(proj["reference"], ref, w0, w1 - w0); ref_args = ["--reference", str(ref)]
    chord_args = ["--chords", proj["chords"]] if proj.get("chords") else []
    subprocess.run([cfg["python"]["analysis"], str(HERE / "canvas.py"), "--score", proj["fit"], "--analysis", proj.get("analysis") or proj["analysis_measured"],
                    "--mix", mix, "--mix-label", proj.get("voice_label", proj.get("voice", "voice")), *(["--recorder-url", proj["recorder_url"]] if proj.get("recorder_url") else []), *[x for v in proj.get("voices", []) for x in ("--voice", f"{v['label']}={(base / v['mix']).resolve() if not str(v['mix']).startswith('/') else v['mix']}")], "--audio-start", str(w0), "--beat-offset", str(proj.get("beat_offset", 0)), "--grid", str(proj.get("score_grid", 4)), *(["--sung", str(Path(proj.get("build", base / "build")) / "sung-score.json")] if (Path(proj.get("build", base / "build")) / "sung-score.json").exists() else []), "--title", title, "-o", str(studio / "canvas"), "--artifact", *ref_args, *chord_args], check=True)
    # other versions of the verse (their own project files) behind version pills; the voice checkbox gets the piano alone
    ver_args = []
    for v in proj.get("versions", []):
        vp = Path(v["project"]) if str(v["project"]).startswith("/") else base / v["project"]
        subprocess.run([sys.executable, str(HERE / "studio.py"), str(vp), "--canvas-only"], check=True)
        vproj, vbase = arrange_config.project(vp)
        ver_args += ["--version", f"{v['label']}={Path(vproj.get('studio', vbase / 'studio')) / 'canvas/index.html'}"]
    subprocess.run([cfg["python"]["plain"], str(HERE / "versions.py"), str(studio / "canvas/index.html"), *ver_args, "--main-label", proj.get("version_label", "Current"),
                    "--piano", str(piano), "--beat-offset", str(proj.get("beat_offset", 0)), "--artifact", "-o", str(studio / "score-canvas.html")], check=True)
    print(f"STUDIO: {studio / 'play-the-line.html'}  (publish with capabilities db)")
    print(f"STUDIO: {studio / 'score-canvas.html'}")


if __name__ == "__main__":
    main()
