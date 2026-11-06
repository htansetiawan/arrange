#!/usr/bin/env python3
"""center.py — find where a voice is comfortable and the key that puts the song there (/arrange-lyrics; numpy).

    python center.py --voice voices/NAME --song lyric-fit.json            # the recommended shift and why
    python center.py --voice voices/NAME --song lyric-fit.json --json out.json --audition 5

A copied voice sounds like its singer only where that singer actually sings. The voice's centre is read from the
singer's whole separated recording (pre/vocal_f0.npy, 50 frames a second, every voiced frame), not from the 10-second
reference clip, which is usually a chorus and sits high. The song's centre is the duration-weighted middle of the
melody it will sing. Four rules. They are options, not one right answer: the script prints all four and the
composer hears the candidates. Three have no tuned numbers; topnote has one (the 90th percentile), chosen on a first
listening test and frozen before the blind test that confirmed it (references/keys.md).
  topnote    the song's highest note lands on the singer's 90th-percentile note (high but still everyday singing)
  top        the shift closest to `median` that keeps the song's 90th-percentile note at or below the singer's own
  median     shift = singer's median note − song's median note
  clip       singer's reference-clip median − song's median                       (the older transpose.py rule)
How often each agreed with a composer's ear (keys heard side by side, 8 voices, one song; mean semitones off,
+ = too high): topnote 1.5 (no lean), top 3.0 (+2.8), median 6.0 (+6.0). See references/keys.md.
--rule picks which one fills `recommended`. Default topnote: it agreed most with the ear (references/keys.md says how
that was measured and why it works); the others stay available and are always printed.
The shift is what the voice sings relative to the written melody. It is also split into a piano key (−6..+5) and an
octave, because moving the piano more than about 3 semitones leaves audible processing, while an octave costs nothing.
--audition N lists N shifts around the recommendation, 2 semitones apart, for the composer to hear; the keys between
topnote and top are printed too, since the ear's choice most often lay there. The rule proposes, the ear decides.
"""
import argparse, json
from pathlib import Path

import numpy as np

FPS = 50   # SoulX preprocessing writes one f0 value every 20 ms


def midi(f0):
    f0 = np.asarray(f0, float)
    return 69 + 12 * np.log2(f0[f0 > 0] / 440)


def clip_notes(prompt):
    d = json.load(open(prompt)); d = d[0] if isinstance(d, list) else d
    p = [int(x) for x in d["note_pitch"].split()]; du = [float(x) for x in d["duration"].split()]
    return np.repeat([x for x in p if x > 0], [max(1, int(t * FPS)) for x, t in zip(p, du) if x > 0])


def voice_profile(vd):
    vd = Path(vd); f0 = vd / "pre/vocal_f0.npy"
    clip = None
    if (vd / "prompt-candidates.json").exists():
        clip = float(json.load(open(vd / "prompt-candidates.json"))[0]["median"])
    elif (vd / "prompt.json").exists():
        clip = float(np.median(clip_notes(vd / "prompt.json")))
    if f0.exists():
        m = midi(np.load(f0)); src = f"whole recording, {len(m) / FPS:.0f} s sung"
    elif (vd / "prompt.json").exists():
        m = clip_notes(vd / "prompt.json"); src = "reference clip only (no whole recording)"
    else:
        raise SystemExit(f"{vd}: no pitch data (pre/vocal_f0.npy or prompt.json)")
    m = m[(m > np.percentile(m, 1)) & (m < np.percentile(m, 99))]   # octave errors and stray frames
    q = np.percentile(m, [10, 25, 50, 75, 90])
    return {"source": src, "p10": q[0], "p25": q[1], "median": q[2], "p75": q[3], "p90": q[4], "clip_median": clip}


def song_profile(path):
    rows = [r for r in json.load(open(path))["rows"] if r.get("kind") == "note"]
    p = np.repeat([r["pitch"] for r in rows], [max(1, int(round((r["end"] - r["t"]) * FPS))) for r in rows])
    q = np.percentile(p, [10, 50, 90])
    return {"notes": len(rows), "p10": q[0], "median": q[1], "p90": q[2], "low": int(p.min()), "high": int(p.max())}


def split(shift):
    key = ((shift + 6) % 12) - 6
    return {"key": int(key), "octave": int((shift - key) // 12)}


def recommend(v, s):
    med = int(round(v["median"] - s["median"]))
    ok = [k for k in range(-24, 13) if s["p90"] + k <= v["p90"]] or [-24]
    top = min(ok, key=lambda k: (abs(k - med), k))
    out = {"topnote": int(round(v["p90"] - s["high"])), "top": top, "median": med}
    if v["clip_median"] is not None:
        out["clip"] = int(round(v["clip_median"] - s["median"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", required=True); ap.add_argument("--song", required=True)
    ap.add_argument("--rule", default="topnote", choices=["topnote", "top", "median", "clip"])
    ap.add_argument("--audition", type=int, default=0); ap.add_argument("--json")
    a = ap.parse_args()
    v, s = voice_profile(a.voice), song_profile(a.song)
    rules = recommend(v, s); best = rules[a.rule]
    aud = [best + 2 * (i - (a.audition - 1) // 2) for i in range(a.audition)] if a.audition else []
    name = Path(a.voice).name
    print(f"{name}: centre {v['median']:.1f} (comfortable {v['p10']:.0f}-{v['p90']:.0f}, {v['source']}); "
          f"song centre {s['median']:.0f}, top {s['p90']:.0f}, highest {s['high']}")
    print("  rules: " + ", ".join(f"{k} {x:+d}" for k, x in rules.items()))
    sp = split(best)
    print(f"  recommended ({a.rule}): sing {best:+d} = piano key {sp['key']:+d}" + (f", octave {sp['octave']:+d}" if sp["octave"] else "")
          + f"; song centre lands on {s['median'] + best:.0f}, its top on {s['p90'] + best:.0f}")
    if aud:
        print("  audition: " + " ".join(f"{x:+d}" for x in aud))
    lo, hi = sorted((rules["topnote"], rules["top"]))
    between = list(range(lo, hi + 1))
    if len(between) > 1:
        print("  topnote to top: " + " ".join(f"{x:+d}" for x in between))
    if a.json:
        json.dump({"voice": name, "voice_profile": v, "song_profile": s, "rules": rules, "rule": a.rule, "recommended": best,
                   **split(best), "audition": aud, "topnote_to_top": between}, open(a.json, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
