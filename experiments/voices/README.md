# Copied voices: what transfers, and what the measures miss

Paper: Section 5.3, "What today's voice models transfer", and Section 5.4, "A score that rose while the ear said
worse".

The composer can give a short sample of a voice for the singer to copy. These experiments ask three things. Do the
singing and conversion models keep the notes in tune? Which system does the composer prefer, heard blind? Do
automatic measures of singing agree with his ear?

| Part | Folder | What was done |
|---|---|---|
| In tune | `voice-check/` | Each render of Color Purple was pitch-tracked note by note against the score (pYIN) and compared with the singer's reference by a speaker-verification model (Resemblyzer). `voice_check.py` |
| Which system | `systems/` | 30 blind clips: SoulX-Singer and Seed-VC paired on the same song, singer and key (9 pairs), TechSinger's three built-in singers on the three songs (9), and one hidden repeat per system (3) |
| Fine-tuning | `finetune/`, `voice-check/` | Seed-VC fine-tuned on the author's own singing; similarity to his reference clip before and after |
| Measures and the ear | `ratings/`, `measures/` | 24 blind clips (21 song and voice items plus 3 hidden repeats), rated 0 to 100, and eleven automatic measures on the voice stem behind each clip. `measure.py` |

The study of eight voices by two routes (the table in Section 5.3) was judged by ear. The verdicts in its last column,
the composer's sighted guess of 60 to 70 for TechSinger, and his verdict on the fine-tuned voice ("worse, layered like
a duet") are his statements and have no data file.

## Reproduce the paper's numbers

No model, audio or network is needed. Python 3 with NumPy and SciPy.

```
python3 paper_numbers.py
```

| Paper | Value | Where in the output | Source |
|---|---|---|---|
| In the four voices measured, 97 to 100% of notes within a quarter tone, typically 10 cents off | 97% to 100%; 9.2 to 10.8 cents in the voice check | `[5.3]` first line | `voice-check/voice-check.json`; Color Purple rows of `measures/measures.csv` |
| A blind test of 35 clips | 30 | `[5.3]` | `systems/` |
| SoulX-Singer 95.9, Seed-VC 88.5 | 95.4, 90.0 | `[5.3]` | `systems/` |
| SoulX higher by 7.4 (95% bootstrap CI 1.9 to 13.3), better on 8 of 10 pairs, Wilcoxon p = 0.049 | +5.4, 0.8 to 10.3, 7 of 9, 0.098 | `[5.3]` | `systems/` |
| TechSinger 22.8, every clip tagged as glitching | 22.8; 9 of 9 | `[5.3]` | `systems/` |
| Hidden repeats within 4 points on average | 1, 0, 11: mean 4.0 | `[5.3]` | `systems/` |
| 8.6 minutes of the author's singing, 113 clips | 518.8 s, 113 | `[5.4]` | `finetune/finetune-clips.json` |
| Similarity to his reference clip 0.88 to 0.92 | 0.876 to 0.920 | `[5.4]` | `voice-check/voice-check.json` |
| 34 blind-rated clips | 24 clips, 21 items | `[5.4]` | `ratings/` |
| 31 clips rated 72 to 100 | 21 items, 72 to 100 | `[5.4]` | `ratings/`, `measures/` |
| No rank correlation above 0.31 in size, none significant | largest 0.329 (naturalness predictor, p = 0.15) | `[5.4]` last block | `ratings/`, `measures/` |

## Songs not distributed

The paper's numbers for Sections 5.3 and 5.4 were computed with data from two further songs, which the author chose not
to distribute. Their clips, ratings and measures are left out here: 5 of the 35 system clips (one SoulX / Seed-VC pair
and three TechSinger clips) and 14 of the 38 rating clips (one hidden repeat and its first hearing among them). No kept
clip lost its pair or its repeat. `paper_numbers.py` on this repository prints the numbers for the distributed songs.
The pitch check and the fine-tuning numbers are the same. These differ:

| Number | Paper | This repository |
|---|---|---|
| System test: clips (SoulX, Seed-VC, TechSinger, repeats) | 35 (10, 10, 12, 3) | 30 (9, 9, 9, 3) |
| SoulX and Seed-VC mean scores | 95.9, 88.5 | 95.4, 90.0 |
| SoulX minus Seed-VC (95% bootstrap CI) | +7.4 (1.9 to 13.3) | +5.4 (0.8 to 10.3) |
| SoulX better on | 8 of 10 pairs | 7 of 9 pairs |
| Wilcoxon p | 0.049 | 0.098 |
| TechSinger clips tagged as glitching | 12 of 12 | 9 of 9 |
| Rated clips (hidden repeats); song x voice items | 38 (4); 34 | 24 (3); 21 |
| Items without TechSinger | 31 | 21 |
| Largest rank correlation in size | 0.31 (vibrato rate, p = 0.09) | 0.33 (naturalness predictor, p = 0.15) |
| Smallest p of the eleven measures | 0.09 | 0.15 |
| Extra columns above 0.31 | none | voiced share, rho +0.71 |

The TechSinger mean (22.8), the system repeats (1, 0, 11; mean 4.0) and the rated range (72 to 100) are unchanged.
The per-measure correlations are in the output of `paper_numbers.py`.

Notes on the definitions:

- In tune. The four voices are the author, Groban, Ingram and Pavarotti, the ones that transferred. The voice check
  covers the author and Ingram as targets of every route (SoulX score mode, SoulX conversion, Seed-VC zero-shot, and
  Seed-VC fine-tuned for the author), plus the Groban-voiced source that the conversions start from (9 renders, 29
  notes each). The Color Purple rating stems add Pavarotti, Groban and the author's two routes. A note is in tune
  within 50 cents of the score plus the render's shift; "cents off" is the median over notes.
- The system test. SoulX and Seed-VC are compared on first hearings only. The paired differences are bootstrapped
  10,000 times (percentile interval, `numpy.random.default_rng(0)`); the Wilcoxon signed-rank test is SciPy's exact
  test. A repeat is compared with its first hearing.
- Fine-tuning. Similarity is the cosine between speaker embeddings (Resemblyzer) of the converted Color Purple line and
  the author's reference clip. Against a held-out stretch of the same recording it rose only from 0.791 to 0.809. Both
  stretches come from a recording that also supplied 33 of the 113 training clips.
- Measures and the ear. "Clips" in the paper are song and voice items: the two hearings of a repeated clip are
  averaged (Pavarotti's 75 and 90 become 82.5). The paper's 31 items left out TechSinger's voices (ids `ts-*`); none of
  the distributed rating clips is a TechSinger voice. Rank
  correlation is Spearman's rho between each measure and the composer's score. The paper's eight measures map to these
  columns: naturalness predictor `singmos_pro`; energy of the singer's ring `spr_db`; pitch movement within notes
  `steady_cents`; vibrato `vib_rate_hz`, `vib_extent_cents`, `vib_frac`; pitch error against the score
  `pitch_err_cents`; harmonics-to-noise ratio `hnr_db`; word error `wer` and `cer`; speaker similarity `likeness`. The
  script also prints four extra columns. With all the paper's clips none passed 0.31; on the distributed clips the
  voiced share does (rho +0.71, n = 21).
- Voice ids for the author's own voice: `henry`, `mine`, `own-score`, `own-seedvc` and `henry-yard`.

## The automatic measures

`measure.py` measures the voice stem behind each clip, not the mix, over the same 15 s of source time as the clip.
Notes come from the song's sung score (`build/studio/sung-score.json`, note rows, at written pitch). The expected sung
pitch is the score pitch plus the stem's shift (`stems.py`); for the conversion and TechSinger stems the shift is
inferred as the rounded median deviation.

| Column | Method |
|---|---|
| `align_lag_s`, `align_corr` | Check only. Cross-correlation of the stem against the mix clip at 8 kHz. All 21 stems: lag 0, correlation 0.70 to 0.95 |
| `spr_db` | Singing power ratio: on voiced frames, the highest level of the long-term spectrum in 2 to 4 kHz minus the highest in 0 to 2 kHz, in dB. `spr_energy_db`: total energy 2 to 4 kHz over 0 to 2 kHz |
| `steady_cents` | Pitch movement within notes: each note of 0.3 s or more, ends trimmed by 15% (at least 40 ms), 4 to 8 Hz removed (vibrato), then the standard deviation in cents; median over notes |
| `vib_frac`, `vib_rate_hz`, `vib_extent_cents` | Vibrato on notes of 0.6 s or more: the largest spectral peak of the detrended pitch in 2 to 12 Hz counts as vibrato if it lies in 4.5 to 8 Hz with at least 15 cents. Share of notes with vibrato; median rate and extent |
| `pitch_err_cents`, `pitch_within50` | Median absolute deviation of each note's median pitch from score plus shift; share of notes within 50 cents |
| `hnr_db` | Harmonics-to-noise ratio, Praat cross-correlation method via parselmouth (10 ms step, 75 Hz floor); mean over voiced frames. `hnr_median_db`: the median |
| `wer`, `cer` | Whisper large-v3-turbo (CPU, temperature 0, no lyric prompt) against the score's words whose first note starts in the window, in English |
| `likeness` | Resemblyzer cosine between the stem window and the singer's reference clip (`likeness_ref`). TechSinger voices have no reference |
| `singmos_pro` | SingMOS-Pro predicted opinion score (1 to 5), on 16 kHz 15 s windows |
| `voiced_frac` | Share of voiced pYIN frames in the window |

Pitch is tracked with pYIN (librosa, 60 to 1100 Hz) for voicing and with YIN with parabolic interpolation for cents,
kept where the two agree within 100 cents.

## Stored data

| Path | Content |
|---|---|
| `voice-check/spec.json` | The 9 renders, the singers' reference and held-out stretches, the score window. Paths are relative to the Color Purple project's `build/` folder; `format` is the audio suffix |
| `voice-check/voice-check.json` | Per render: notes, share within 50 cents, median cents off, similarity to the reference and to the held-out stretch |
| `systems/key.json` | The 30 clip codes: song, system, voice, shift, repeat, and the mix by name |
| `systems/answers/composer_<code>.json` | The composer's score (0 to 100), tags and position in the page |
| `ratings/key.json`, `ratings/order.json` | The 24 clip codes: song, voice, mix path in the song project (no suffix), excerpt start; the order shown |
| `ratings/answers/composer_<code>.json` | The composer's score, tags and position |
| `measures/measures.csv` | One row per clip code (a repeat copies its twin's values), every measure |
| `finetune/finetune-clips.json` | The 113 fine-tuning clips: name, seconds, sample rate |

## What is not distributed

- Audio: the rated clips and mixes, the voice stems, the renders in the voice check, the singers' reference clips and
  recordings, and the author's 113 training clips. Most singers did not consent to publication of their voices; the
  author's recordings stay private. Clips are referred to by code and renders by name.
- The fine-tuned Seed-VC weights (trained on the author's voice).
- The rating pages. They played the clips from the claude.ai artifact runtime.
- The sung scores of the songs (note-level melodies with lyrics), which `measure.py` and `voice_check.py` read. For the
  same reason the recognised and expected words (`asr_hyp`, `asr_ref`) are removed from `measures.csv`.

## Rerun

Every step below needs the song projects (`ARRANGE_RUNS`, one folder per song as written by the skills) and writes to
`build/`, so the stored data are not overwritten. Most steps need a GPU or private audio.

```
python3 voice_check.py voice-check/spec.json --base $ARRANGE_RUNS/color-purple/build -o build/voice-check.json
python3 ratings/make_clips.py                     # the clips of the 5.4 rating set
python3 measure.py                                # build/measures/*.json and measures.csv
python3 systems/render_systems.py                 # the system comparison: stems and mixes (GPU)
python3 systems/make_clips.py                     # its clips and key
python3 finetune/finetune_data.py DATASET_DIR     # the fine-tuning clips
```

The fine-tuning used Seed-VC (commit 51383ef) with its preset config and default settings (batch 2, 1,000 steps; 57
steps per epoch on these 113 clips), on one GPU, from the Seed-VC checkout:

```
python train.py --config ./configs/presets/config_dit_mel_seed_uvit_whisper_base_f0_44k.yml --dataset-dir DATASET_DIR --run-name RUN_NAME
```

Models: SoulX-Singer (commit 81aeb3a; score mode and its SVC converter), Seed-VC (commit 51383ef;
`Plachta/Seed-VC` `DiT_seed_v2_uvit_whisper_base_f0_44k_bigvgan_pruned_ft_ema.pth` with
`nvidia/bigvgan_v2_44khz_128band_512x`; 50 diffusion steps, f0 conditioning, no automatic f0 adjustment), TechSinger
(commit cd5bd27; built-in singers EN-Alto-1, EN-Alto-2, EN-Tenor-1; `systems/sing_techsinger.py`), Resemblyzer 0.1.4,
openai-whisper with `large-v3-turbo`, praat-parselmouth, jiwer, SingMOS (commit 1554e86, `singmos_pro`, with s3prl;
torch and torchaudio 2.8.0, since s3prl calls `torchaudio.set_audio_backend`). Every measure ran on the CPU.

| Variable | Used for | Default |
|---|---|---|
| `ARRANGE_RUNS` | song projects: mixes, stems, sung scores, voices | `runs/` at the repository root |
| `ARRANGE_ANALYSIS_PY` | Python with librosa and scipy (`measure.py` acoustic stage; `polish.py`) | the current Python |
| `ARRANGE_ASR_PY` | Python with openai-whisper, parselmouth, jiwer | the current Python |
| `ARRANGE_WHISPER_DIR` | where Whisper keeps its checkpoint | Whisper's default |
| `ARRANGE_VC_PY` | Python with Resemblyzer (likeness) and Seed-VC | the current Python |
| `ARRANGE_SINGMOS_PY`, `ARRANGE_SINGMOS`, `ARRANGE_SINGMOS_HUB` | Python for SingMOS, the SingMOS checkout, the torch hub folder | the current Python; none; torch's default |
| `ARRANGE_SEEDVC` | Seed-VC checkout | the current folder |
| `ARRANGE_TS_PY`, `ARRANGE_TECHSINGER` | Python for TechSinger, the TechSinger checkout | the current Python; the current folder |
| `ARRANGE_SING_SCRIPTS` | folder with the skill's `sing.py` | `skills/arrange-lyrics/scripts` |
