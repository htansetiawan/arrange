#!/usr/bin/env python3
"""show_fit.py — print the project's fit as the Score Canvas numbers it, the pronounce file, and the sounds the singer gets (plain python).

    python show_fit.py arrange-project.json [--no-sounds]

Columns: idx (the row number edit_fit.py takes), bar.beat (as the canvas shows them, in the composer's count),
no. (the grey number under each sung syllable on the canvas), t - end (seconds in the recording), pitch, kind,
text, word. The sounds need the g2p python (setting python.soulx); --no-sounds skips them.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fitlib  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("project"); ap.add_argument("--no-sounds", action="store_true"); a = ap.parse_args()
P = fitlib.load(a.project); rows = P["fit"]["rows"]; c = P["canvas"]
print(f"Song: {P['proj'].get('title', 'Untitled')}, {c.ts}.\n")
print("FIT:\n" + fitlib.table(rows, c))
print("\nPRONOUNCE FILE: " + json.dumps(P["pron"], ensure_ascii=False))
if not a.no_sounds:
    try:
        print("\nSOUNDS THE SINGER GETS NOW (sung rows, start time, syllable: sounds):\n" + fitlib.sounds(rows, P["pron"]))
    except (RuntimeError, OSError) as e:
        print(f"\nSOUNDS: not available ({e})")
