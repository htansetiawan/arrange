#!/usr/bin/env python3
"""sing.py — the fit, sung in a chosen voice and mixed over the recording, in one step (/arrange-lyrics; plain python).

    python sing.py arrange-project.json [--voice NAME --shift -12] [--n-steps 64] [--seed 1234] [--takes 3] [--try]

Reads the project file (fit, recording, window, voice, voice_shift, build), then:
phonemes for the sung rows (legato through the piano's grey notes) -> SoulX
score-mode render with the voice's reference clip -> a check of where the voice
actually enters at every line start -> the voice mixed over the recording for
the project's window. A voice is a folder under the configured voices_dir with
prompt.wav, prompt.json and CONSENT.txt; "english" is SoulX's bundled singer.
A voice without CONSENT.txt is refused.

Takes: SoulX samples, so every render is a new take unless the seed is fixed. --takes N renders N takes
(listening only; the project is left alone) and prints each one's seed; rank them with check_takes.py and
listen. Keep one by running sing.py again with --seed <its seed>: the same take is rendered and the
project records it as voice_take (voice, shift, seed, steps, guidance). Later runs with the same voice
and shift reuse those settings unless told otherwise.
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); import arrange_config  # noqa: E402
RENDER = HERE.parents[1] / "arrange-render/scripts/backends/soulx.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project"); ap.add_argument("--voice"); ap.add_argument("--shift", type=int)
    ap.add_argument("--n-steps", type=int, help="flow-matching steps: 32 (SoulX default) or 64 (finer, slower)"); ap.add_argument("--cfg", type=float)
    ap.add_argument("--seed", type=int, help="the take's starting noise: the same seed on the same fit gives the same take")
    ap.add_argument("--takes", type=int, default=1, help="render this many takes for listening (seeds seed, seed+1, ...)")
    ap.add_argument("--try", dest="trial", action="store_true", help="render for listening only: leave the project's voice_mix as it is")
    a = ap.parse_args()
    cfg = arrange_config.load(); proj, base = arrange_config.project(a.project)
    voice = a.voice or proj.get("voice", "english"); shift = a.shift if a.shift is not None else int(proj.get("voice_shift", 0))
    kept = proj.get("voice_take") or {}; kept = kept if (kept.get("voice"), kept.get("shift")) == (voice, shift) else {}
    a.n_steps = a.n_steps or kept.get("n_steps", 32); a.cfg = a.cfg if a.cfg is not None else kept.get("cfg", 3.0)
    seed = a.seed if a.seed is not None else (kept.get("seed") if a.takes == 1 else None)
    trial = a.trial or a.takes > 1
    build = Path(proj.get("build", base / "build")); build.mkdir(parents=True, exist_ok=True)
    score = build / "sung-score.json"
    pron = ["--pronounce", proj["pronounce"]] if proj.get("pronounce") else []
    subprocess.run([cfg["python"]["soulx"], str(HERE / "phonemes.py"), proj["fit"], str(score), "--legato", "--legato-max", str(proj.get("legato_max", 1.6)), *pron], check=True)
    if voice == "english":
        prompt_args = ["--prompt", "english"]
    else:
        vd = Path(arrange_config.require(cfg, "voices_dir")) / voice
        if not (vd / "CONSENT.txt").exists():
            sys.exit(f"REFUSED: the voice '{voice}' has no CONSENT.txt in {vd}; record who agreed and for what use first")
        prompt_args = ["--prompt", f"{voice}={vd / 'prompt.wav'}:{vd / 'prompt.json'}"]
    out = build / "voice"
    subprocess.run([cfg["python"]["soulx"], str(RENDER), "--score", str(score), "--spine", proj["recording"], "--out", str(out), *prompt_args,
                    "--pairs", f"{voice}:{shift}", "--n-steps", str(a.n_steps), "--cfg", str(a.cfg), "--takes", str(a.takes),
                    *(["--seed", str(seed)] if seed is not None else [])], check=True)
    cands = json.load(open(out / "candidates.json"))["candidates"]
    if all(c["status"] != "rendered" for c in cands):
        sys.exit("the voice render failed: " + cands[0].get("error", "")[-400:])
    tag = "" if (a.n_steps, a.cfg) == (32, 3.0) else f"-steps{a.n_steps}-cfg{a.cfg:g}"
    w = proj.get("window", [0, 70])
    for n, cand in enumerate(cands, 1):
        if cand["status"] != "rendered":
            print(f"take {n} (seed {cand['seed']}) failed: {cand.get('error', '')[-200:]}"); continue
        take = f"-take{n}" if a.takes > 1 else ""
        mix = build / f"voice-mix-{voice}{shift:+d}{tag}{take}.mp3" if trial else build / f"voice-mix-{voice}.mp3"
        subprocess.run([cfg["python"]["analysis"], str(HERE / "mixcheck.py"), "--voice", cand["path"], "--score", str(score), "--recording", proj["recording"],
                        "--window", str(w[0]), str(w[1]), "-o", str(mix), "--report", str(build / "entries.json")], check=True)
        print(f"SUNG{' (trial, project unchanged)' if trial else ''}: {mix}  seed {cand['seed']}")
    if a.takes > 1:
        print(f"rank: python check_takes.py --score {score} --window {w[0]} {w[1]} " + " ".join(f"--take {c['id']}:{shift}:{c['path']}" for c in cands if c["status"] == "rendered"))
        print(f"keep one: python sing.py {a.project} --voice {voice} --shift {shift} --n-steps {a.n_steps} --cfg {a.cfg:g} --seed <its seed>")
    if trial:
        return
    proj_raw = json.loads(Path(a.project).read_text()); proj_raw["voice_mix"] = str(mix.relative_to(base)) if str(mix).startswith(str(base)) else str(mix)
    proj_raw["voice_take"] = {"voice": voice, "shift": shift, "seed": cands[0]["seed"], "n_steps": a.n_steps, "cfg": a.cfg}
    Path(a.project).write_text(json.dumps(proj_raw, indent=1))


if __name__ == "__main__":
    main()
