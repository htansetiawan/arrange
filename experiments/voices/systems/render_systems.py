#!/usr/bin/env python3
"""render_systems.py: the balanced system comparison of Section 5.3. The same song, singer and key sung by SoulX-Singer
directly and by SoulX-Groban re-voiced with Seed-VC; TechSinger's three built-in singers on every song. Every
clip is mixed by the same polish call, so only the singing system differs. Needs a GPU.

    python3 render_systems.py            # ../build/systems/stems/, mixes/, manifest.json

Paths and interpreters (environment variables; each Python defaults to the current one):
  ARRANGE_RUNS         song projects (recordings, sung scores, voices)
  ARRANGE_ANALYSIS_PY  Python for skills/arrange-render/scripts/polish.py
  ARRANGE_VC_PY        Python for Seed-VC; ARRANGE_SEEDVC = the Seed-VC checkout (inference.py)
  ARRANGE_TS_PY        Python for TechSinger; ARRANGE_TECHSINGER = the TechSinger checkout
  ARRANGE_SING_SCRIPTS folder with the skill's sing.py (default skills/arrange-lyrics/scripts); sing_techsinger.py is here
Seed-VC and TechSinger write WAV; each is converted to MP3 and the WAV deleted at once.
"""
import json, os, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
env = lambda k, d=None: os.environ.get(k, d)
RUNS = Path(env("ARRANGE_RUNS", REPO / "runs")); S = Path(env("ARRANGE_SING_SCRIPTS", REPO / "skills/arrange-lyrics/scripts"))
PY, VC, TSPY = env("ARRANGE_ANALYSIS_PY", sys.executable), env("ARRANGE_VC_PY", sys.executable), env("ARRANGE_TS_PY", sys.executable)
SEEDVC, TECHSINGER = env("ARRANGE_SEEDVC"), env("ARRANGE_TECHSINGER")
OUT = Path(__file__).resolve().parents[1] / "build/systems"
VOICES = RUNS / "color-purple/voices"
MP3, WAV = "mp3", "wav"   # audio suffixes

# run: (recording for a piano key k, window), pairs (target voice, sung shift, piano key)
SONGS = {
    "all-the-things-cohen": {"rec": lambda k: f"source/recording-key{k:+d}.{WAV}", "win": (0, 75),
                             "pairs": [("bolton", -4, -4), ("clarkson", 2, 2), ("adams", -1, -1)], "tenor": 0},
    "color-purple": {"rec": lambda k: f"source/recording-key{k:+d}.{WAV}", "win": (0, 70),
                     "pairs": [("bolton", -11, 1), ("adams", -6, -6)], "tenor": -12},
    "someday-my-prince": {"rec": lambda k: f"source/recording-key{k:+d}.{WAV}", "win": (0, 42),
                          "pairs": [("ariana", -2, -2), ("clarkson", 1, 1), ("bolton", -11, 1)], "tenor": -12},
}
TS = ["EN-Tenor-1", "EN-Alto-1", "EN-Alto-2"]


def sh(cmd, **kw):
    print("+", cmd if isinstance(cmd, str) else " ".join(map(str, cmd))[:300], flush=True)
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)


def to_mp3(wav, mp3):
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3)], check=True)
    os.remove(wav)


def polish(run, stem, k, out):
    c = SONGS[run]; d = RUNS / run
    rec = c["rec"](k) if run != "color-purple" or k != 0 else f"source/recording-key+0.{WAV}"
    sh([PY, REPO / "skills/arrange-render/scripts/polish.py", "--voice", stem, "--recording", d / rec, "--score", d / "build/studio/sung-score.json",
        "--window", str(c["win"][0]), str(c["win"][1]), "--preset", "touch", "-o", out], check=True, stdout=subprocess.DEVNULL)


def soulx_stem(run, voice, shift):
    stem = RUNS / run / f"build/studio/voice/{voice}{shift:+d}.{MP3}"
    if not stem.exists():
        sh([sys.executable, S / "sing.py", RUNS / run / "arrange-project.json", "--voice", voice, "--shift", str(shift), "--n-steps", "64", "--try"],
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return stem


def main():
    (OUT / "stems").mkdir(parents=True, exist_ok=True); (OUT / "mixes").mkdir(exist_ok=True)
    manifest = []
    for run, c in SONGS.items():
        w0, w1 = c["win"]
        for v, s, k in c["pairs"]:
            # SoulX twin: the target voice sung directly
            st = soulx_stem(run, v, s)
            mx = OUT / f"mixes/{run}__soulx__{v}{s:+d}.{MP3}"
            if st.exists() and not mx.exists(): polish(run, st, k, mx)
            manifest.append({"song": run, "system": "SoulX", "voice": v, "shift": s, "key": k, "stem": str(st), "mix": str(mx)})
            # Seed-VC: Groban sung by SoulX at the same shift, re-voiced as the target
            g = soulx_stem(run, "groban", s)
            vs = OUT / f"stems/{run}__seedvc__{v}{s:+d}.{MP3}"; mx = OUT / f"mixes/{run}__seedvc__{v}{s:+d}.{MP3}"
            if g.exists() and not vs.exists():
                tmp = OUT / f"tmp-{run}-{v}"; tmp.mkdir(exist_ok=True)
                sh(["ffmpeg", "-v", "error", "-y", "-ss", str(w0), "-t", str(w1 - w0), "-i", g, "-ac", "1", "-ar", "44100", tmp / f"source.{WAV}"], check=True)
                sh([VC, "inference.py", "--source", tmp / f"source.{WAV}", "--target", VOICES / v / f"prompt.{WAV}", "--output", tmp / "out",
                    "--diffusion-steps", "50", "--f0-condition", "True", "--auto-f0-adjust", "False", "--semi-tone-shift", "0", "--fp16", "False"],
                   cwd=SEEDVC, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                outs = sorted((tmp / "out").glob(f"*.{WAV}"))
                if outs:
                    sh(["ffmpeg", "-v", "error", "-y", "-i", outs[0], "-af", f"adelay={int(w0 * 1000)}:all=1", "-c:a", "libmp3lame", "-b:a", "128k", vs], check=True)
                sh(["rm", "-rf", str(tmp)])
            if vs.exists() and not mx.exists(): polish(run, vs, k, mx)
            manifest.append({"song": run, "system": "Seed-VC", "voice": v, "shift": s, "key": k, "stem": str(vs), "mix": str(mx), "source": str(g)})
        # TechSinger: built-in singers, altos at the written pitch, the tenor an octave down on high songs
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", RUNS / run / SONGS[run]["rec"](0)],
                                   capture_output=True, text=True).stdout or 300)
        for sg in TS:
            s = c["tenor"] if "Tenor" in sg else 0
            vs = OUT / f"stems/{run}__techsinger__{sg}{s:+d}.{MP3}"; mx = OUT / f"mixes/{run}__techsinger__{sg}{s:+d}.{MP3}"
            if not vs.exists():
                wav = OUT / f"tmp-{run}-{sg}.{WAV}"
                sh([TSPY, Path(__file__).resolve().parent / "sing_techsinger.py", RUNS / run / "build/studio/sung-score.json", "--singer", sg, "--shift", str(s), "--length", f"{dur:.0f}", "-o", wav],
                   cwd=TECHSINGER, env={**os.environ, "PYTHONPATH": "."}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if wav.exists(): to_mp3(wav, vs)
            if vs.exists() and not mx.exists(): polish(run, vs, 0, mx)
            manifest.append({"song": run, "system": "TechSinger", "voice": sg, "shift": s, "key": 0, "stem": str(vs), "mix": str(mx)})
    json.dump(manifest, open(OUT / "manifest.json", "w"), indent=1)
    done = [m for m in manifest if Path(m["mix"]).exists()]
    print(f"DONE {len(done)}/{len(manifest)} mixes; missing: {[Path(m['mix']).name for m in manifest if not Path(m['mix']).exists()]}")


if __name__ == "__main__":
    main()
