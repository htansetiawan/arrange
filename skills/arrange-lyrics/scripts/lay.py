#!/usr/bin/env python3
"""lay.py — lay the composer's lines on a skeleton from a chosen slot, phrase by phrase, applying the fitting tricks (/arrange-lyrics step 4; analysis python).

    python lay.py --skeleton jobs/skeleton-1-16/skeleton.json --analysis piano-analysis.json --start-slot 32 --lines lines.txt -o jobs/verse1/ [--title ...] [--transpose -12]

Each line goes on the next phrase (the first from the chosen slot). When a line
has more syllables than the phrase has slots, the longest notes are split into
two repeated notes (as "lan-terns"); when fewer, the last word is held over
the spare notes. Every change is written down in words. Output: lyric-fit.json
(rows: time, pitch, syllable, hold, word; no phonemes yet), a notation picture
with the words, an ABC, report.txt. Words come only from the composer's lines.
"""
import argparse, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "arrange-plan/scripts"))
from clock import Clock  # noqa: E402
import notate  # noqa: E402

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


_RIGHT_PAIRS = {"bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl", "pr", "tr", "th", "sh", "ch", "ph", "wh"}
_LEFT_PAIRS = {"ng", "ck"}


def _split_at_vowel_groups(word):
    """One part per vowel group; the consonants between two groups are divided the way a
    singer reads them: one consonant starts the next syllable (wa-king), a blend or digraph
    stays together (a-cross), ng/ck stay behind (strang-ers), otherwise split after the
    first (foot-steps, win-dows)."""
    # y between two vowels starts a syllable (la-yer, be-yond); elsewhere it is a vowel (sky, ev-er-y)
    groups = [(m.start(), m.end()) for m in re.finditer(r"(?:[aeiou]|y(?![aeiou])|y(?=e[ds]?$))+", word, flags=re.I)]
    if word.lower() in ("eye", "eyes", "bye", "byes", "dye", "rye", "lye", "aye", "ayes"):
        return [word]
    if word[:1].lower() == "y" and groups and groups[0][0] == 0 and groups[0][1] > 1:
        groups[0] = (1, groups[0][1])   # a leading y is a consonant: yes, yearned
    if len(groups) <= 1:
        return [word]
    cuts = []
    for (_, e1), (s2, _) in zip(groups, groups[1:]):
        c = word[e1:s2].lower()
        if len(c) <= 1:
            cut = e1
        elif c[:2] in _LEFT_PAIRS:
            cut = e1 + 2 if len(c) > 2 else s2
        elif len(c) == 2:
            cut = e1 if c in _RIGHT_PAIRS else e1 + 1
        else:
            cut = e1 + 1
        cuts.append(cut)
    bounds = [0] + cuts + [len(word)]
    return [word[a:b] for a, b in zip(bounds, bounds[1:])]


def syllabify_text(word):
    parts = _split_at_vowel_groups(word)
    w = word.lower()
    last = parts[-1].lower() if len(parts) > 1 else ""
    if last and re.fullmatch(r"[^aeiouy]{0,4}(e|es|ed)", last) and not w.endswith(("le", "les", "led", "ee", "ye")) \
            and not (last.endswith("ed") and re.search(r"[td]ed$", w)):
        parts[-2] += parts[-1]; parts.pop()   # silent e: wel-come, breeze, o-pened
    if re.search(r"[^aeiouy]l(e|es|ed)$", w) and len(parts) >= 1:
        # consonant + le is its own syllable: set-tles, ta-ble, gen-tle
        m = re.search(r"([^aeiouy]l(?:e|es|ed))$", word, flags=re.I).group(1)
        head = word[: len(word) - len(m)]
        if re.search(r"[aeiouy]", head, flags=re.I):
            parts = syllabify_text(head) + [m] if head.lower() != w else parts
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", required=True); ap.add_argument("--analysis", required=True); ap.add_argument("--start-slot", type=int, required=True)
    ap.add_argument("--lines", required=True); ap.add_argument("-o", "--out", required=True); ap.add_argument("--title", default="The lines on the melody"); ap.add_argument("--transpose", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sk = json.load(open(a.skeleton)); line, phrases, slots = sk["line"], sk["phrases"], sk["slots"]
    clk = Clock(json.load(open(a.analysis)))
    lines = [ln.strip() for ln in Path(a.lines).read_text().splitlines() if ln.strip() and not ln.startswith("[")]
    # slot numbering as the picture shows it
    slot_no, n = {}, 0
    for k, s in enumerate(slots):
        if s:
            n += 1; slot_no[k] = n
    start_k = next(k for k, v in slot_no.items() if v == a.start_slot)
    report = [f"words begin at slot {a.start_slot} (bar {line[start_k]['bar']}, {line[start_k]['t']:.1f} s)"]
    rows = [dict(r) for r in line]
    for r in rows:
        r["text"], r["kind"], r["word"], r["placed"] = "", "unsung", None, "piano melody (extracted)"
    pi = next(i for i, p in enumerate(phrases) if start_k in p)
    li = 0
    queue = [list(p) for p in phrases[pi:]]
    first = True; pn = pi
    while queue and li < len(lines):
        p = queue.pop(0); pn += 1
        ks = [k for k in p if slot_no.get(k) and (k >= start_k if first else True)]
        first = False
        ln = lines[li]
        syl = [(s, w) for w in re.findall(r"[A-Za-z']+", ln) for s in syllabify_text(w)]
        have, need = len(ks), len(syl)
        if have > need + 3:
            # a phrase much longer than the line: cut it at the clearest rest after the line's syllables and keep the rest for the next line
            cands = [(rows[ks[j + 1]]["t"] - rows[ks[j]]["end"], j) for j in range(need - 1, min(have - 1, need + 3))]
            gap, j = max(cands)
            keep, rest = ks[:j + 1], ks[j + 1:]
            queue.insert(0, [k for k in p if k > keep[-1]])
            report.append(f"phrase {pn}: {have} slots for a {need}-syllable line; cut at the rest after slot {slot_no[keep[-1]]} ({gap:.2f} s); the remaining {len(rest)} notes go to the next line")
            ks = keep; have = len(ks)
        li += 1
        if need > have:
            extra = need - have
            longest = sorted(ks, key=lambda k: -(rows[k]["end"] - rows[k]["t"]))[:extra]
            for k in sorted(longest, reverse=True):
                r = rows[k]; mid = round(r["t"] + (r["end"] - r["t"]) / 2, 3)
                second = dict(r); second["t"] = mid; r["end"] = mid; second["placed"] = "split by the tool: two syllables on one repeated note"
                rows.insert(k + 1, second)
                report.append(f"phrase {pn}: '{ln}' has {need} syllables for {have} slots: the {NAMES[r['pitch'] % 12]}{r['pitch'] // 12 - 1} at bar {r['bar']} ({r['t']:.1f} s) is split into two repeated notes")
            # recompute the slot list after insertions: everything from the first slot of this phrase onward, in order
            ks = sorted(set(ks) | set(range(min(ks), min(ks) + need)))[:need]
            ks = list(range(min(ks), min(ks) + need))
        for j, k in enumerate(ks):
            r = rows[k]
            if j < need:
                s, w = syl[j]; r["text"], r["kind"], r["word"] = s, "note", w
            else:
                r["text"], r["kind"], r["word"] = "~", "slur", syl[-1][1]
        if have > need:
            held = [rows[k] for k in ks[need:]]
            report.append(f"phrase {pn}: '{ln}' has {need} syllables for {have} slots: '{syl[-1][1]}' is held over {len(held)} spare note(s) ({', '.join(NAMES[h['pitch'] % 12] + str(h['pitch'] // 12 - 1) for h in held)})")
        elif have == need:
            report.append(f"phrase {pn}: '{ln}' fits {need} slots one syllable per note")
        # rows were inserted for splits: shift every later index in the queue
        inserted = len(rows) - len(line)
        if inserted:
            base = max(ks)
            queue = [[k + inserted if k > base else k for k in q] for q in queue]
            slot_no = {(k + inserted if k > base else k): v for k, v in slot_no.items()}; line = rows[:]
    if li < len(lines):
        report.append(f"{len(lines) - li} line(s) left for the next bars: " + " / ".join(lines[li:]))
    sung = [r for r in rows if r["kind"] != "unsung"]
    for r in rows:
        r["pitch"] = r["pitch"] + a.transpose
    for k, r in enumerate(rows):
        r["index"] = k
    json.dump({"skeleton": a.skeleton, "start_slot": a.start_slot, "transpose": a.transpose, "lines": lines[:li], "rows": rows, "report": report}, open(out / "lyric-fit.json", "w"), indent=1, ensure_ascii=False)
    q = notate.quantise([dict(r) for r in sung], clk, 4)
    notate.write_abc(q, out / "fit.abc", a.title); notate.write_musicxml(q, out / "fit.musicxml", a.title, 4); notate.engrave(out / "fit.musicxml", out / "fit.svg", out / "fit.png")
    (out / "report.txt").write_text("\n".join(report) + "\n")
    for r in report:
        print("LAY:", r)
    print(" ".join(r["text"] for r in sung))


if __name__ == "__main__":
    main()
