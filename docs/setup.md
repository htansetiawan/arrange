# Setting up the ARRANGE skills

The five skills in `skills/` are folders in the Agent Skills format. Install them
side by side (for Claude Code, copy or link the five folders into
`.claude/skills/` of a project or `~/.claude/skills/`): several scripts import
shared code from a sibling skill, for example `clock.py` from `arrange-plan`.

Nothing in the skills names a path on a particular machine. Where the Python
environments, models and voices live is set once, in a config file or in
environment variables, as below.

## The config file and environment variables

The scripts read a JSON file: `$ARRANGE_CONFIG` if set, else
`$XDG_CONFIG_HOME/arrange/config.json`, else `~/.config/arrange/config.json`.
`skills/arrange-lyrics/config.example.json` lists every key; copy it and edit.
The file is optional: an environment variable overrides the file, and a setting
that neither gives falls back to the default below. A script that needs a
setting that is missing stops and names both the key and the variable.

| Setting (config key) | Environment variable | Default | Used by |
|---|---|---|---|
| `python.analysis` | `ARRANGE_PYTHON_ANALYSIS` | the Python running the script | `studio.py` (canvas), `sing.py` (entry check), `make_voice.py` (clip ranking) |
| `python.soulx` | `ARRANGE_PYTHON_SOULX` | the Python running the script | `sing.py` (phonemes, SoulX), `make_voice.py` (preprocessing), `show_fit.py` (sounds) |
| `python.plain` | `ARRANGE_PYTHON` | the Python running the script | `studio.py`, `merge_take.py` |
| `soulx.repo` | `ARRANGE_SOULX_REPO` | none (required for singing) | `backends/soulx.py`, `make_voice.py`, `convert_voice.py` |
| `soulx.checkpoint` | `ARRANGE_SOULX_CHECKPOINT` | `<repo>/pretrained_models/SoulX-Singer/model.pt` | `backends/soulx.py`; `convert_voice.py` uses `model-svc.pt` beside it |
| `voices_dir` | `ARRANGE_VOICES_DIR` | none (required for a voice other than SoulX's bundled `english`) | `sing.py`, `make_voice.py`, `transpose.py --for-voice` |
| `device` | `ARRANGE_DEVICE` | `cuda` | SoulX, ACE-Step, Demucs (`hear.py`), SoulX preprocessing; set `cpu` to run without a GPU (slow) |
| `whisper.model` | `ARRANGE_WHISPER_MODEL` | `large-v3-turbo` | `check_takes.py` |
| `whisper.cache` | `ARRANGE_WHISPER_CACHE` | Whisper's own (`~/.cache/whisper`) | `check_takes.py` |
| `ace_step.repo` | `ARRANGE_ACESTEP_REPO` | none (required for instrument layers) | `backends/ace_step.py` |
| `ace_step.checkpoints` | `ARRANGE_ACESTEP_CHECKPOINTS` | an existing `ACESTEP_CHECKPOINTS_DIR`, else `<repo>/checkpoints` | `backends/ace_step.py` |
| `ace_step.hf_home` | `ARRANGE_HF_HOME` | an existing `HF_HOME`, else the Hugging Face default | `backends/ace_step.py` |
| `ytdlp` | `ARRANGE_YTDLP` | `yt-dlp` on `PATH` | `make_voice.py` with a link (only for recordings you have the right to use) |
| `chrome` | `ARRANGE_CHROME` | `google-chrome`, `chromium` or `chromium-browser` on `PATH` | `notate.py` (optional PNG of the score) |
| (none) | `ARRANGE_KONG_CHECKPOINT` | the package's own path | `transcribe.py` (or `--checkpoint`) |

Paths inside a song project (`arrange-project.json`: recording, analysis, fit,
pronounce file) are relative to the project file and never go in the config.

## Python environments

The scripts work in one environment that has everything, but the models pin
different library versions, so three environments are usual. Each config key
`python.*` names the interpreter for one role.

- **plain**: Python 3.10 or later, standard library only. The plan scripts
  (`arrange-brainstorm`, `arrange-plan`), `smf.py`, `stub.py`, `register.py`,
  and in `arrange-lyrics`: `studio.py`, `recorder.py`, `versions.py`,
  `editor.py`, `merge_take.py`, `take.py`, `sing.py`, `make_voice.py`,
  `transpose.py`, `show_fit.py`, `edit_fit.py`.
- **analysis**: numpy, soundfile, librosa, pretty_midi, music21, verovio,
  pedalboard, pyloudnorm, scipy. Used by `analyze.py`, `canvas.py`,
  `notate.py`, `skeleton.py`, `lay.py`, `dictate.py`, `repitch.py`, `align.py`,
  `center.py`, `pick_prompt.py`, `mixcheck.py`, `mix.py`, `verify.py`,
  `export.py`, `polish.py`.
- **soulx**: the SoulX-Singer requirements plus `g2p_en`. Used by
  `backends/soulx.py`, `phonemes.py`, `fit.py`, `convert_voice.py` and SoulX's
  preprocessing. `g2p_en` downloads NLTK data (`averaged_perceptron_tagger`,
  `cmudict`) on first use; fetch it once before working offline.

Optional, each in whichever environment suits: `piano_transcription_inference`
and torch (`transcribe.py`), `openai-whisper` (`check_takes.py`), `demucs`
(`hear.py`), and ACE-Step's own environment (`backends/ace_step.py`).

## Models

| Model | What it does here | Where to get it | How the scripts find it |
|---|---|---|---|
| SoulX-Singer | score-mode singing in a voice copied from a 10-15 s clip; its SVC checkpoint re-voices a sung track | code: github.com/Soul-AILab/SoulX-Singer; weights: `hf download Soul-AILab/SoulX-Singer --local-dir pretrained_models/SoulX-Singer` (gives `model.pt` and `model-svc.pt`) | `soulx.repo`, `soulx.checkpoint` |
| SoulX-Singer preprocessing | separates the voice from the band (Mel-Band RoFormer karaoke and dereverb models), tracks pitch (RMVPE), recognises the words and transcribes the sung notes; used by `make_voice.py` and the sung-reference way in | `hf download Soul-AILab/SoulX-Singer-Preprocess --local-dir pretrained_models/SoulX-Singer-Preprocess`, inside the SoulX-Singer folder | relative to `soulx.repo` |
| Kong et al. high-resolution piano transcription | piano audio to MIDI with pedal (`transcribe.py`) | `pip install piano_transcription_inference`; the checkpoint (`note_F1=0.9677_pedal_F1=0.9186.pth`, from Zenodo record 4034264) downloads with `wget` on first use into `~/piano_transcription_inference_data/` | the package default, or `ARRANGE_KONG_CHECKPOINT` / `--checkpoint` |
| Demucs (`htdemucs_6s`) | separates the voice from a sung reference in `hear.py` (an alternative to SoulX's separator) | `pip install demucs`; weights download through torch hub on first use (`TORCH_HOME` sets where) | the package default |
| Whisper (`large-v3-turbo`) | lists words a sung take swallowed (`check_takes.py`) | `pip install openai-whisper`; weights download on first use | `whisper.model`, `whisper.cache` |
| ACE-Step 1.5 (`acestep-v15-xl-base`) | adds one instrument layer to the recording (Lego task, `backends/ace_step.py`); needs a base DiT, not sft or turbo | code: github.com/ace-step/ACE-Step-1.5; weights: huggingface.co/ACE-Step/acestep-v15-xl-base plus the shared models of huggingface.co/ACE-Step/Ace-Step1.5 (VAE, text encoder) in the checkpoints folder | `ace_step.repo`, `ace_step.checkpoints`, `ace_step.hf_home` |
| g2p_en | English words to ARPAbet sounds (CMU dictionary plus a neural guesser) | `pip install g2p_en` and its NLTK data | the soulx environment |
| Resemblyzer | not used by this release (a speaker-similarity check from the paper's experiments is not included) | - | - |

The backends run offline (`HF_HUB_OFFLINE=1`): download the weights first.
SoulX-Singer and ACE-Step want a CUDA GPU; ACE-Step's XL models need about
12 GB of GPU memory with offloading (20 GB or more recommended by its authors).

## External tools

- **ffmpeg**, built with `libmp3lame` (every MP3 written) and the `rubberband`
  filter (`transpose.py` moves the piano's key with it, formants preserved).
  Taken from `PATH`.
- **Chrome or Chromium** (optional): headless, for the PNG of an engraved score
  in `notate.py`. Without it the SVG pages are written and the PNG is skipped.
- **yt-dlp** (optional): `make_voice.py` with a video link.
- **git** (optional): `ace_step.py` records the ACE-Step revision it ran.
- **A browser** for the two pages. Play the Line uses the Web Audio API and,
  for a MIDI keyboard, Web MIDI (Chrome or Edge). The Score Canvas embeds its
  engraving; only `versions.py --upload` loads Verovio's WebAssembly build from
  jsDelivr when the page is opened.

## Hosting the pages

`studio.py` writes self-contained HTML (audio embedded). Opened from disk, the
recorder downloads each take as JSON and copies it to the clipboard; give the
file to the agent. Hosted as a claude.ai artifact with the `db` capability, the
recorder saves takes and the beat grid to the artifact's store, where the agent
reads them. No other service is contacted.

## A quick offline check

With no model, no GPU and no network, these run on the shipped examples
(plain Python):

```
K=skills
python3 $K/arrange-plan/scripts/validate.py $K/arrange-plan/examples/arrangement.example.json $K/arrange-plan/examples/piano-analysis.example.json
python3 $K/arrange-plan/scripts/tracks.py $K/arrange-plan/examples/arrangement.example.json $K/arrange-plan/examples/piano-analysis.example.json tracks.html
python3 $K/arrange-brainstorm/scripts/coverage.py $K/arrange-brainstorm/examples/ARRANGEMENT.example.md $K/arrange-listen/examples/piano-analysis.example.json
```
