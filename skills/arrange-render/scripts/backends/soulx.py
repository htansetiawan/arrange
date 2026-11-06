#!/usr/bin/env python3
"""soulx.py — score-route vocal backend: SoulX-Singer on a fitted score, placed on the recording's clock (SoulX python).

    python soulx.py --score jobs/L1/score.json --spine piano.wav --out build/L1 [--shifts 0 -12] [--prompt english] \
        [--n-steps 64] [--cfg 3] [--seed 1234] [--takes 3] [--soulx-repo DIR] [--checkpoint model.pt] [--device cuda]

The SoulX-Singer repository, checkpoint and device come from the flags, else from the ARRANGE
settings (soulx.repo, soulx.checkpoint, device in the config file, or ARRANGE_SOULX_REPO,
ARRANGE_SOULX_CHECKPOINT, ARRANGE_DEVICE); the checkpoint defaults to
<repo>/pretrained_models/SoulX-Singer/model.pt. See docs/setup.md.

Builds SoulX's target metadata from score.json (one row per note: phoneme,
duration, MIDI pitch; rests as <SP>; slurs as note type 3), cuts the bundled
English prompt to its own metadata window, runs the SoulX CLI in score
control mode once per pitch shift, resamples the result to the spine's rate
and places it at the first note's time inside a full-length, zero-aligned
stem. Writes candidates.json: per candidate the shift, the sample count
check against the spine (done on PCM before the MP3 is written and the PCM
removed), peak, RMS over the sung window, elapsed seconds, backend version
and the hashes of its inputs. Nothing musical is judged here.

Takes and seeds: SoulX samples (flow matching from random noise), so the same score sung twice is two
different takes: how long each sound lasts inside a note, when a consonant lands, the colour of a vowel.
--seed fixes the starting noise, so the same score, voice, shift, steps, guidance and seed give the same
take again. Without --seed a random one is drawn; either way every candidate records its seed. --takes N
renders N takes per voice and shift with seeds seed, seed+1, ..., named <voice><shift>-take1..N.
A changed score gives a different take even with the same seed (the noise follows the length).
"""
import re, argparse, hashlib, json, os, secrets, subprocess, sys, tempfile, time
from pathlib import Path

import numpy as np
import soundfile as sf
import librosa

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "arrange-lyrics/scripts"))
import arrange_config  # noqa: E402


# SoulX's CLI never seeds its sampler: seed every generator, then run the CLI unchanged as __main__
SEEDED = ("import sys, random, runpy, numpy, torch; s = int(sys.argv[1]); random.seed(s); numpy.random.seed(s); "
          "torch.manual_seed(s); torch.cuda.manual_seed_all(s); sys.argv = ['cli.inference'] + sys.argv[2:]; "
          "runpy.run_module('cli.inference', run_name='__main__', alter_sys=True)")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def target_rows(rows, shift):
    out, t = [], None
    for r in rows:
        if t is None:
            t = r["t"]
        if r["t"] - t > 0.02:
            out.append(("<SP>", "<SP>", round(r["t"] - t, 3), 0, 1))
        dur = round(max(0.05, r["end"] - r["t"]), 3)
        if r["kind"] == "unsung" or not r["phoneme"]:
            out.append(("<SP>", "<SP>", dur, 0, 1))
        else:
            out.append((r["text"] if r["kind"] == "note" else "~", r["phoneme"], dur, r["pitch"] + shift, 2 if r["kind"] == "note" else 3))
        t = r["t"] + dur
    out.append(("<SP>", "<SP>", 0.3, 0, 1))
    return out


def metadata(rows, index):
    total = sum(r[2] for r in rows)
    return [{"index": index, "language": "English", "time": [0, int(round(total * 1000))],
             "duration": " ".join(f"{r[2]:.3f}" for r in rows), "text": " ".join(r[0] for r in rows),
             "phoneme": " ".join(r[1] for r in rows), "note_pitch": " ".join(str(r[3]) for r in rows),
             "note_type": " ".join(str(r[4]) for r in rows)}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True); ap.add_argument("--spine", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--shifts", type=int, nargs="*", default=[0, -12])
    ap.add_argument("--prompt", action="append", default=[], help="name=prompt.wav:metadata.json, or 'english' for SoulX's bundled singer; repeatable")
    ap.add_argument("--pairs", nargs="*", default=[], help="prompt:shift pairs to render, e.g. english:0 english:-12 myvoice:-12; default = every prompt at every shift")
    ap.add_argument("--n-steps", type=int, default=32, help="flow-matching steps (SoulX default 32; more = slower, finer)")
    ap.add_argument("--cfg", type=float, default=3.0, help="classifier-free guidance (SoulX default 3)")
    ap.add_argument("--seed", type=int, help="starting noise; the same seed on the same score gives the same take (default: a random one, recorded)")
    ap.add_argument("--takes", type=int, default=1, help="takes per voice and shift, seeds seed, seed+1, ... (named -take1, -take2, ...)")
    ap.add_argument("--soulx-repo", help="the SoulX-Singer repository (default: setting soulx.repo)")
    ap.add_argument("--checkpoint", help="the SoulX-Singer model.pt (default: setting soulx.checkpoint, else <repo>/pretrained_models/SoulX-Singer/model.pt)")
    ap.add_argument("--device", help="cuda or cpu (default: setting device)")
    a = ap.parse_args()
    cfg = arrange_config.load()
    SX = Path(a.soulx_repo or arrange_config.require(cfg, "soulx.repo")).resolve()
    CKPT = Path(a.checkpoint or arrange_config.get(cfg, "soulx.checkpoint") or SX / "pretrained_models/SoulX-Singer/model.pt").resolve()
    device = a.device or arrange_config.get(cfg, "device", "cuda")
    seed0 = a.seed if a.seed is not None else secrets.randbelow(2 ** 31 - 1000)
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)   # the SoulX CLI runs from its own folder: every path must be absolute
    a.score, a.spine = str(Path(a.score).resolve()), str(Path(a.spine).resolve())
    score = json.load(open(a.score)); rows = [r for r in score["rows"]]
    input_hashes = {"score": sha(a.score), "spine": sha(a.spine)}   # taken at the start: what this run actually used
    t0 = rows[0]["t"]
    info = sf.info(a.spine); spine_frames, sr = info.frames, info.samplerate
    prompts = {}
    for spec in (a.prompt or ["english"]):
        if spec == "english":
            prompts["english"] = (SX / "example/audio/en_prompt.mp3", SX / "example/audio/en_prompt.json")
        else:
            name, rest = spec.split("=", 1); wav, meta = rest.split(":", 1); prompts[name] = (Path(wav).resolve(), Path(meta).resolve())
    prepared = {}
    for name, (prompt, meta) in prompts.items():
        pm = json.load(open(meta)); start, end = pm[0]["time"]
        pwav = out / f"prompt-{name}.temporary.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(start / 1000), "-i", str(prompt), "-t", str((end - start) / 1000), "-ar", "24000", "-ac", "1", str(pwav)], check=True)
        pm[0]["time"] = [0, end - start]; pmeta = out / f"prompt-{name}-metadata.json"; pmeta.write_text(json.dumps(pm, ensure_ascii=False))
        prepared[name] = (pwav, pmeta, prompt)
    pairs = [(p.split(":")[0], int(p.split(":")[1])) for p in a.pairs] or [(nm, sh) for nm in prompts for sh in a.shifts]
    if not CKPT.exists():
        sys.exit(f"REFUSED: the SoulX checkpoint is not reachable at {CKPT}")
    config = "soulxsinger/config/soulxsinger.yaml"
    if (a.n_steps, a.cfg) != (32, 3.0):   # the CLI takes steps and guidance only from the config file
        txt = (SX / config).read_text()
        txt = re.sub(r"(?m)^(  n_steps:).*$", rf"\1 {a.n_steps}", txt, count=1); txt = re.sub(r"(?m)^(  cfg:).*$", rf"\1 {a.cfg}", txt, count=1)
        cpath = out / f"soulxsinger-steps{a.n_steps}-cfg{a.cfg:g}.yaml"; cpath.write_text(txt); config = str(cpath.resolve())
    cands = []
    for (name, shift), k in [(pr, k) for pr in pairs for k in range(a.takes)]:
        pwav, pmeta, prompt = prepared[name]
        cid = f"{name}{shift:+d}" + (f"-take{k + 1}" if a.takes > 1 else ""); seed = seed0 + k
        work = out / cid; work.mkdir(exist_ok=True)
        tgt = metadata(target_rows(rows, shift), f"L_{cid}")
        (work / "soulx-target.json").write_text(json.dumps(tgt, ensure_ascii=False))
        cmd = [sys.executable, "-c", SEEDED, str(seed), "--device", device, "--model_path", str(CKPT), "--config", config,
               "--prompt_wav_path", str(pwav), "--prompt_metadata_path", str(pmeta), "--target_metadata_path", str(work / "soulx-target.json"),
               "--phoneset_path", "soulxsinger/utils/phoneme/phone_set.json", "--save_dir", str(work), "--control", "score"]
        t = time.time()
        r = subprocess.run(cmd, cwd=SX, env={**os.environ, "PYTHONPATH": str(SX), "HF_HUB_OFFLINE": "1"}, capture_output=True, text=True)
        el = time.time() - t
        (work / "soulx.log").write_text(r.stdout[-4000:] + "\n--- stderr ---\n" + r.stderr[-4000:])
        gen = work / "generated.wav"
        if r.returncode != 0 or not gen.exists():
            cands.append({"id": cid, "shift": shift, "voice": name, "seed": seed, "status": "failed", "elapsed_s": round(el, 1), "error": r.stderr[-600:]}); continue
        y, ysr = sf.read(gen, dtype="float32", always_2d=True); y = y.mean(axis=1)
        if ysr != sr:
            y = librosa.resample(y, orig_sr=ysr, target_sr=sr)
        stem = np.zeros((spine_frames, 2), dtype=np.float32)
        i0 = int(round(t0 * sr)); n = min(len(y), spine_frames - i0)
        stem[i0:i0 + n, 0] = y[:n]; stem[i0:i0 + n, 1] = y[:n]
        pcm = work / "stem.temporary.wav"; sf.write(pcm, stem, sr, subtype="PCM_24")
        with sf.SoundFile(pcm) as f:
            frames_ok = f.frames == spine_frames and f.samplerate == sr
        mp3 = out / f"{cid}.mp3"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(pcm), "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
        pcm.unlink(); gen.unlink()
        sung = stem[i0:i0 + n, 0]
        cands.append({"id": cid, "shift": shift, "voice": name, "seed": seed, "n_steps": a.n_steps, "cfg": a.cfg, "status": "rendered", "path": str(mp3), "elapsed_s": round(el, 1), "generated_sr": ysr, "generated_s": round(len(y) / sr, 3),
                      "placed_at_s": t0, "frames_match_spine": frames_ok, "peak": round(float(np.abs(sung).max()), 4), "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(sung ** 2)) + 1e-9)), 1),
                      "parents": {**input_hashes, "prompt": sha(prompt), "checkpoint": str(CKPT)}, "backend": "soulx-singer score mode"})
        print(f"{cid} (seed {seed}): {el:.0f}s, {len(y)/sr:.1f}s of voice placed at {t0}s, frames ok {frames_ok}, peak {cands[-1]['peak']}, rms {cands[-1]['rms_db']} dB")
    for pwav, _, _ in prepared.values():
        pwav.unlink()
    json.dump({"layer_job": "soulx-singer", "score": a.score, "spine": a.spine, "candidates": cands}, open(out / "candidates.json", "w"), indent=1)


if __name__ == "__main__":
    main()
