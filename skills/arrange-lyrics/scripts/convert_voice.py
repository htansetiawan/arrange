#!/usr/bin/env python3
"""convert_voice.py — re-voice a sung track in another singer's sound with SoulX's voice conversion (/arrange-lyrics; SoulX python).

    python convert_voice.py --sung build/studio/voice/english-12.mp3 --voice voices/ref --clip 1 \
        --window 26 68 --shift 12 -o build/studio/voice/ref-svc.wav

Score-based singing (sing.py) needs the reference singer's words transcribed, so it
fails for a language SoulX does not know (Italian, for example) and for clips whose
words came out garbled. Voice conversion needs no words: it keeps the sung track's
notes, words and timing and swaps only the sound of the voice, copied from a clip of
the reference singer. The clip is taken from <voice>/prompt-candidates.json (ranked by
pick_prompt.py / make_voice.py). The output sits on the same clock as the sung track.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sung", required=True, help="the sung voice track to re-voice (on the recording's clock)")
    ap.add_argument("--voice", required=True, help="voice folder with pre/vocal.wav and prompt-candidates.json")
    ap.add_argument("--clip", type=int, default=1, help="which ranked clip of the reference singer")
    ap.add_argument("--window", type=float, nargs=2, required=True, help="seconds of the sung track to convert")
    ap.add_argument("--shift", type=int, default=0, help="semitones to move the sung track (12 = up an octave)")
    ap.add_argument("--n-steps", type=int, default=64); ap.add_argument("--cfg", type=float, default=3.0)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    cfg = arrange_config.load(); sx = Path(arrange_config.require(cfg, "soulx.repo")).resolve()
    ckpt = Path(arrange_config.get(cfg, "soulx.checkpoint") or sx / "pretrained_models/SoulX-Singer/model.pt").with_name("model-svc.pt")
    device = arrange_config.get(cfg, "device", "cuda")
    if not ckpt.exists():
        sys.exit(f"REFUSED: the voice-conversion checkpoint is missing at {ckpt}")
    vd = Path(a.voice)
    if not (vd / "CONSENT.txt").exists():
        sys.exit(f"REFUSED: {vd} has no CONSENT.txt")
    clip = json.load(open(vd / "prompt-candidates.json"))[a.clip - 1]
    t0, t1 = a.window
    with tempfile.TemporaryDirectory(prefix="arrange-svc-") as tmp:
        tmp = Path(tmp); pw, tw = tmp / "prompt.wav", tmp / "target.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(clip["t"][0]), "-t", str(clip["t"][1] - clip["t"][0]), "-i", str(vd / "pre/vocal.wav"), "-ac", "1", "-ar", "24000", str(pw)], check=True)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(Path(a.sung).resolve()), "-ac", "1", "-ar", "24000", str(tw)], check=True)
        code = f"""
import sys; sys.path.insert(0, {str(sx)!r})
from preprocess.tools.f0_extraction import F0Extractor
f = F0Extractor(model_path='pretrained_models/SoulX-Singer-Preprocess/rmvpe/rmvpe.pt', device={device!r})
f.process({str(pw)!r}, f0_path={str(tmp / 'prompt_f0.npy')!r}); f.process({str(tw)!r}, f0_path={str(tmp / 'target_f0.npy')!r})
"""
        subprocess.run([sys.executable, "-c", code], cwd=sx, check=True, capture_output=True)
        conf = (sx / "soulxsinger/config/soulxsinger.yaml").read_text()
        import re
        conf = re.sub(r"(?m)^(  n_steps:).*$", rf"\1 {a.n_steps}", conf, count=1); conf = re.sub(r"(?m)^(  cfg:).*$", rf"\1 {a.cfg}", conf, count=1)
        (tmp / "conf.yaml").write_text(conf)
        r = subprocess.run([sys.executable, "-m", "cli.inference_svc", "--device", device, "--model_path", str(ckpt), "--config", str(tmp / "conf.yaml"),
                            "--prompt_wav_path", str(pw), "--target_wav_path", str(tw), "--prompt_f0_path", str(tmp / "prompt_f0.npy"),
                            "--target_f0_path", str(tmp / "target_f0.npy"), "--save_dir", str(tmp / "out"), "--pitch_shift", str(a.shift)],
                           cwd=sx, env={**os.environ, "PYTHONPATH": str(sx), "HF_HUB_OFFLINE": "1"}, capture_output=True, text=True)
        gen = tmp / "out/generated.wav"
        if r.returncode or not gen.exists():
            sys.exit("voice conversion failed: " + r.stderr[-800:])
        y, sr = sf.read(gen, dtype="float32")
        full = np.zeros(int(round(t1 * sr)) + len(y), dtype=np.float32); i0 = int(round(t0 * sr)); full[i0:i0 + len(y)] = y
        sf.write(a.out, full, sr)
    print(f"CONVERTED: {a.out}  ({vd.name}, clip {a.clip}: {clip['t'][0]:.1f}-{clip['t'][1]:.1f} s, shift {a.shift:+d}, {a.n_steps} steps)")


if __name__ == "__main__":
    main()
