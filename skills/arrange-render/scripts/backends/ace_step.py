#!/usr/bin/env python3
"""ace_step.py — audio-route backend: ACE-Step 1.5 Lego ("add a layer") on the plan's declared context (ACE-Step python).

    python ace_step.py --plan arrangement.json --layer L2 --spine piano.wav --build build/ [--variants 3] [--seed 20261031]

Materialises the context exactly as the plan declares it (the piano plus the
chosen candidate of every id in conditions.audio_context, loudness-matched
to the piano), runs the Lego task once per variant with the plan's prompt
and class, pads or trims each result to the recording's length, keeps the
plan's interval [t0, t1) with short fades (ACE generates the whole length;
the plan decides where the layer sounds), checks the exact frame count on
PCM, writes MP3 candidates and candidates.json with parents' hashes, seeds,
elapsed time and peak memory. The recipe (xl-base, 50 steps, guidance 7, no
LM planning, instrumental) is a fixed default. No musical judgement here.

Where ACE-Step lives comes from the ARRANGE settings (docs/setup.md): ace_step.repo
(ARRANGE_ACESTEP_REPO), ace_step.checkpoints (ARRANGE_ACESTEP_CHECKPOINTS, else an existing
ACESTEP_CHECKPOINTS_DIR, else <repo>/checkpoints), ace_step.hf_home (ARRANGE_HF_HOME, else an
existing HF_HOME), and device (ARRANGE_DEVICE). Runs offline: the models must already be downloaded.
"""
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "arrange-lyrics/scripts"))
import arrange_config  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True); ap.add_argument("--layer", required=True); ap.add_argument("--spine", required=True)
    ap.add_argument("--build", required=True); ap.add_argument("--variants", type=int, default=3); ap.add_argument("--seed", type=int, default=20261031)
    ap.add_argument("--model", default="acestep-v15-xl-base"); ap.add_argument("--steps", type=int, default=50); ap.add_argument("--guidance", type=float, default=7.0)
    a = ap.parse_args()
    cfg = arrange_config.load()
    ACE = Path(arrange_config.require(cfg, "ace_step.repo")).resolve()
    CKPT = arrange_config.get(cfg, "ace_step.checkpoints") or os.environ.get("ACESTEP_CHECKPOINTS_DIR") or str(ACE / "checkpoints")
    HF = arrange_config.get(cfg, "ace_step.hf_home") or os.environ.get("HF_HOME")
    device = arrange_config.get(cfg, "device", "cuda")
    os.environ.update(ACESTEP_CHECKPOINTS_DIR=str(CKPT), HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", ACESTEP_GENERATION_TIMEOUT="1800")
    if HF:
        os.environ["HF_HOME"] = str(HF)
    import numpy as np
    import soundfile as sf
    import torch

    def load_mono(path, rate):
        """Decode any audio file to mono float32 at `rate` through ffmpeg (no librosa in this venv)."""
        tmp = build / "decode.temporary.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(path), "-ar", str(rate), "-ac", "1", "-c:a", "pcm_f32le", str(tmp)], check=True)
        y, _ = sf.read(tmp, dtype="float32"); tmp.unlink()
        return y
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    plan = json.load(open(a.plan)); L = next(x for x in plan["layers"] if x["id"] == a.layer)
    build = Path(a.build) / a.layer; build.mkdir(parents=True, exist_ok=True)
    piano, sr = sf.read(a.spine, dtype="float32", always_2d=True)
    n = len(piano); piano_rms = float(np.sqrt(np.mean(piano ** 2)))
    # context = piano + chosen candidates of the declared audio context, each matched to the piano's RMS then scaled -3 dB
    ctx = piano.copy(); parents = {"spine": sha(a.spine)}
    for lid in L["conditions"].get("audio_context", []):
        if lid == "piano":
            continue
        src = next(x for x in plan["layers"] if x["id"] == lid)
        cand = next((c for c in src.get("candidates", []) if c["id"] == src.get("chosen")), None)
        if not cand or not cand.get("path"):
            raise SystemExit(f"{lid} has no chosen rendered candidate; the plan's context cannot be built")
        y = load_mono(cand["path"], sr)
        y = np.pad(y, (0, max(0, n - len(y))))[:n]
        rms = float(np.sqrt(np.mean(y ** 2))) or 1e-9
        g = piano_rms / rms * 10 ** (-3 / 20)
        ctx[:, 0] += y * g; ctx[:, 1] += y * g
        parents[lid] = cand["id"]
    ctx *= min(1.0, 0.95 / float(np.abs(ctx).max()))
    ctx_path = build / "context.wav"; sf.write(ctx_path, ctx, sr, subtype="FLOAT")
    parents["context"] = sha(ctx_path); parents["clock"] = plan.get("clock", {}).get("revision", 0)
    prompt = L["job"]["params"]["prompt"]; cls = L["job"]["params"]["track_name"]
    try:
        revision = subprocess.check_output(["git", "-C", str(ACE), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unknown"
    on_cuda = device.startswith("cuda") and torch.cuda.is_available()
    if on_cuda:
        torch.cuda.reset_peak_memory_stats()
    t = time.time()
    handler = AceStepHandler()
    status, ok = handler.initialize_service(project_root=str(ACE), config_path=a.model, device=device, use_flash_attention=False,
                                            compile_model=False, offload_to_cpu=True, offload_dit_to_cpu=False, quantization=None, prefer_source="huggingface")
    if not ok:
        raise SystemExit(status)
    init_s = time.time() - t
    t0, t1 = L["t0"], L["t1"]
    i0, i1 = int(round(t0 * sr)), int(round(t1 * sr))
    fade = int(0.02 * sr)
    cands = []
    for k in range(a.variants):
        seed = a.seed + k
        config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav32")
        params = GenerationParams(task_type="lego", instruction=f"Generate the {cls.upper()} track based on the audio context:", src_audio=str(ctx_path),
                                  caption=prompt + ". Purely instrumental accompaniment; no singing.", lyrics="[Instrumental]", instrumental=True,
                                  vocal_language="unknown", duration=n / sr, inference_steps=a.steps, guidance_scale=a.guidance, seed=seed,
                                  repainting_start=0.0, repainting_end=-1.0, thinking=False, use_cot_metas=False, use_cot_caption=False,
                                  use_cot_language=False, use_cot_lyrics=False, audio_codes="", enable_normalization=False)
        ts = time.time()
        res = generate_music(handler, None, params, config, save_dir=str(build / f"raw-seed{seed}"))
        el = time.time() - ts
        if not res.success or len(res.audios) != 1:
            cands.append({"id": f"seed{seed}", "seed": seed, "status": "failed", "elapsed_s": round(el, 1), "error": str(res.error)[:600]}); continue
        stem, ssr = sf.read(res.audios[0]["path"], dtype="float32", always_2d=True)
        if ssr != sr:
            tmp = build / "resample.temporary.wav"
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", res.audios[0]["path"], "-ar", str(sr), "-c:a", "pcm_f32le", str(tmp)], check=True)
            stem, ssr = sf.read(tmp, dtype="float32", always_2d=True); tmp.unlink()
        raw_len = len(stem) / sr
        stem = np.pad(stem, ((0, max(0, n - len(stem))), (0, 0)))[:n]
        gated = np.zeros_like(stem); gated[i0:i1] = stem[i0:i1]
        ramp = np.linspace(0, 1, fade)[:, None]
        gated[i0:i0 + fade] *= ramp; gated[i1 - fade:i1] *= ramp[::-1]
        pcm = build / f"seed{seed}.temporary.wav"; sf.write(pcm, gated, sr, subtype="PCM_24")
        with sf.SoundFile(pcm) as f:
            frames_ok = f.frames == n and f.samplerate == sr
        mp3 = build / f"seed{seed}.mp3"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(pcm), "-c:a", "libmp3lame", "-b:a", "192k", str(mp3)], check=True)
        pcm.unlink()
        win = gated[i0:i1]
        cands.append({"id": f"seed{seed}", "seed": seed, "status": "rendered", "path": str(mp3), "elapsed_s": round(el, 1), "raw_s": round(raw_len, 2),
                      "window_s": [t0, t1], "frames_match_spine": frames_ok, "peak": round(float(np.abs(win).max()), 4),
                      "rms_db": round(float(20 * np.log10(np.sqrt(np.mean(win ** 2)) + 1e-9)), 1), "backend": f"ace-step/lego {a.model} rev {revision[:8]}",
                      "params": {"steps": a.steps, "guidance": a.guidance, "prompt": prompt, "class": cls}, "parents": {**parents, "prompt": hashlib.sha256(prompt.encode()).hexdigest()[:16]}})
        print(f"seed{seed}: {el:.0f}s, raw {raw_len:.1f}s, gated to {t0}-{t1}s, frames ok {frames_ok}, peak {cands[-1]['peak']}, rms {cands[-1]['rms_db']} dB")
    peak_mem = torch.cuda.max_memory_allocated() / 2 ** 30 if on_cuda else 0.0
    json.dump({"layer_job": "ace-step/lego", "layer": a.layer, "context": str(ctx_path), "audio_context": L["conditions"].get("audio_context"), "init_s": round(init_s, 1),
               "peak_torch_gib": round(peak_mem, 2), "candidates": cands}, open(build / "candidates.json", "w"), indent=1)
    print(f"init {init_s:.0f}s, peak torch memory {peak_mem:.2f} GiB; {sum(c['status']=='rendered' for c in cands)}/{len(cands)} rendered")


if __name__ == "__main__":
    main()
