#!/usr/bin/env python3
"""syllables.py — count syllables per <lyrics> cell vs. melody notes (English heuristic).

    python3 syllables.py ARRANGEMENT.md piano-analysis.json

Prints "verse 2: 31 syllables onto 28 notes" style lines. A mismatch is a
QUESTION for the creator, never an edit. The heuristic is vowel-group
counting with common English exceptions; for other languages (Indonesian is
near-perfectly syllabic by vowel) it is usually right, but say "about".
"""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from notebook import parse  # noqa: E402


def count_word(w: str) -> int:
    w = re.sub(r"[^a-z']", "", w.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    if w.endswith("ed") and not w.endswith(("ted", "ded")) and n > 1:
        n -= 1
    return max(1, n)


def main():
    nb = parse(Path(sys.argv[1]).read_text(encoding="utf-8"))
    an = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else {}
    notes = an.get("melody", {}).get("notes_per_section", {})
    labels = {s["id"]: s["label"].lower() for s in an.get("sections", [])}
    notes_by_label = {labels.get(k, k).lower(): v for k, v in notes.items()}
    for c in nb["cells"]:
        for k in c["components"]:
            if k["type"] == "lyrics":
                syl = sum(count_word(w) for ln in k["lines"] for w in ln.split())
                n = notes_by_label.get(c["name"].lower())
                tail = f" onto {n} melody notes" + ("" if n is None or n == syl else f"  → {'melisma on ' + str(n - syl) + ' note(s)' if n > syl else str(syl - n) + ' syllable(s) need split notes'} — ASK") if n is not None else " (no melody count for this section in the analysis)"
                print(f"{c['name']}: about {syl} syllables{tail}")


if __name__ == "__main__":
    main()
