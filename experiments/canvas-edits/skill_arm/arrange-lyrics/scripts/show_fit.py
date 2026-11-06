#!/usr/bin/env python3
"""show_fit.py — print the sung line as the score canvas numbers it, the pronounce file, and the sounds the singer gets.

    python3 show_fit.py [--song song]
"""
import argparse, json
import fitlib

ap = argparse.ArgumentParser(); ap.add_argument("--song", default="song"); a = ap.parse_args()
fit, pron, clock = fitlib.load(a.song)
print(f"Song: {fit['title']}, {fit['ts']}.\n")
print("FIT:\n" + fitlib.table(fit["rows"]))
print("\nPRONOUNCE FILE: " + json.dumps(pron, ensure_ascii=False))
print("\nSOUNDS THE SINGER GETS NOW (sung rows, start time, syllable: sounds):\n" + fitlib.sounds(fit["rows"], pron))
