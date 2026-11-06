#!/usr/bin/env python3
"""fit.py — put the composer's words on the melody's notes, syllable by syllable (/arrange-lyrics, step 2; a python with g2p_en).

    python fit.py --melody jobs/L1/melody.json --lyrics lyrics.txt -o jobs/L1/score.json [--transpose 0]

Each word is turned into ARPAbet phones (g2p_en) and split into syllables at
its vowels. Syllables are laid on the notes in order. If there are more notes
than syllables, the spare notes become slurs of the previous syllable ("~")
when they follow within a second, otherwise they are left unsung and
reported. If there are more syllables than notes, the surplus is reported and
left out; nothing is rewritten. Written notes the melody fitter could not find
in the performance are placed by interpolation between their neighbours and
flagged. Output: score.json with one row per note: start, end, pitch, text,
phoneme, kind (note|slur|unsung), plus a fit report in plain words.
"""
import argparse, json, re
from pathlib import Path

VOWEL = re.compile(r"^[AEIOU][A-Z]*[012]$")


def syllabify(word, g2p):
    phones = [p for p in g2p(word) if re.fullmatch(r"[A-Z]+[012]?", p)]
    if not phones:
        return []
    vowels = [i for i, p in enumerate(phones) if VOWEL.match(p)]
    if not vowels:
        return [phones]
    sylls, start = [], 0
    for a, b in zip(vowels, vowels[1:]):
        between = b - a - 1
        cut = a + 1 + (0 if between <= 1 else between - 1)   # one consonant goes to the next syllable; more: keep all but one
        sylls.append(phones[start:cut]); start = cut
    sylls.append(phones[start:])
    return sylls


def split_text(word, n):
    if n <= 1:
        return [word]
    parts = re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]*(?=[^aeiouy]*[aeiouy])|[^aeiouy]*$)", word, flags=re.I) or [word]
    while len(parts) > n:
        parts[-2] += parts[-1]; parts.pop()
    while len(parts) < n:
        parts.append("-")
    return parts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--melody", required=True); ap.add_argument("--lyrics", required=True); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--transpose", type=int, default=0); ap.add_argument("--lines", type=int, nargs=2, help="1-based line range to use")
    ap.add_argument("--min-syllable-s", type=float, default=0.2, help="a note shorter than this that follows another note within 0.1 s is a melisma, not a syllable")
    ap.add_argument("--phrase-gap-s", type=float, default=3.0, help="a pause or hold of at least this long between onsets starts a new phrase; lines go on phrases in order")
    ap.add_argument("--edits", help="score.edited.json from the editor: its rows (notes and syllables, splits included) are applied verbatim; only phonemes are computed")
    a = ap.parse_args()
    from g2p_en import G2p
    g2p = G2p()
    if a.edits:
        ed = json.load(open(a.edits))
        rows = sorted(ed["rows"], key=lambda r: r["t"])
        out, report = [], [f"applied the creator's edit of {ed.get('edited_at', '?')}: {len(rows)} notes" + (f"; note: {ed['note']}" if ed.get("note") else "")]
        # group consecutive sung rows that belong to one word (same `word`, marked as parts) and spread its syllables over them
        i = 0
        while i < len(rows):
            r = rows[i]
            text = (r.get("text") or "").strip()
            if text == "" :
                out.append({**r, "text": "", "phoneme": "", "kind": "unsung", "word": None}); i += 1; continue
            if text == "~":
                prev = out[-1] if out else None
                out.append({**r, "text": "~", "phoneme": prev["phoneme"] if prev and prev["phoneme"] else "", "kind": "slur" if prev and prev["phoneme"] else "unsung", "word": prev["word"] if prev else None}); i += 1; continue
            word = (r.get("word") or text).strip()
            group = [i]
            while i + len(group) < len(rows) and (rows[i + len(group)].get("word") or "").strip() == word and (rows[i + len(group)].get("text") or "").strip() not in ("", "~") and rows[i + len(group)].get("part", True) and r.get("part", True) and word != text:
                group.append(i + len(group))
            ph = syllabify(word, g2p) or [[]]
            if len(group) == 1:
                phon = "en_" + "-".join(p for sy in ph for p in sy) if ph and ph[0] else ""
                out.append({**r, "text": text, "phoneme": phon, "kind": "note" if phon else "unsung", "word": word})
            else:
                # spread the word's syllables over its notes; extra notes hold the last syllable, extra syllables pile onto the last note
                per = []
                for k in range(len(group)):
                    if k < len(ph) - 1 or (k == len(group) - 1):
                        per.append([p for sy in ph[k:] for p in sy] if k == len(group) - 1 else ph[k])
                    else:
                        per.append(None)
                for k, gi in enumerate(group):
                    rr = rows[gi]
                    if per[k]:
                        out.append({**rr, "text": rr["text"], "phoneme": "en_" + "-".join(per[k]), "kind": "note", "word": word})
                    else:
                        out.append({**rr, "text": "~", "phoneme": out[-1]["phoneme"], "kind": "slur", "word": word})
            i += len(group)
        for x, y in zip(out, out[1:]):
            if x["end"] > y["t"]:
                x["end"] = round(y["t"], 3)
        for k, r in enumerate(out):
            r["index"] = k
        json.dump({"melody": a.melody, "lyrics": a.edits, "lines": ed.get("lines", []), "transpose": a.transpose, "rows": out, "report": report, "edited": True}, open(a.out, "w"), indent=1, ensure_ascii=False)
        for r in report:
            print("FIT:", r)
        print(" ".join(r["text"] for r in out))
        return
    mel = json.load(open(a.melody))
    notes = sorted(mel["notes"], key=lambda n: n["index"])
    # interpolate unmatched written notes between neighbours
    rows, report = [], []
    by_index = {n["index"]: n for n in notes}
    total = mel["written_notes"]
    for i in range(total):
        if i in by_index:
            n = by_index[i]; rows.append({"index": i, "t": n["t"], "end": n["end"], "pitch": n["written_pitch"] + a.transpose, "placed": "performance"})
        else:
            prev = max((k for k in by_index if k < i), default=None); nxt = min((k for k in by_index if k > i), default=None)
            if prev is None or nxt is None:
                report.append(f"written note {i} has no neighbours to place it between; left out"); continue
            p, q = by_index[prev], by_index[nxt]
            frac = (i - prev) / (nxt - prev)
            t = p["t"] + frac * (q["t"] - p["t"])
            rows.append({"index": i, "t": round(t, 3), "end": round(min(q["t"], t + 0.3), 3), "pitch": mel["unmatched"][[u["index"] for u in mel["unmatched"]].index(i)]["pitch"] + a.transpose, "placed": "interpolated"})
    rows.sort(key=lambda r: r["t"])
    for x, y in zip(rows, rows[1:]):
        if x["end"] > y["t"]:
            x["end"] = round(y["t"], 3)
    lines = [ln.strip() for ln in Path(a.lyrics).read_text().splitlines()]
    lines = [ln for ln in lines if ln and not ln.startswith("[")]
    if a.lines:
        lines = lines[a.lines[0] - 1:a.lines[1]]
    sylls = []
    for ln in lines:
        for word in re.findall(r"[A-Za-z']+", ln):
            ph = syllabify(word, g2p)
            texts = split_text(word, len(ph))
            for k, (tx, p) in enumerate(zip(texts, ph)):
                sylls.append({"word": word, "text": tx, "phoneme": "en_" + "-".join(p), "line": ln})
    # which notes can carry a syllable: the first note of any run, and any note long enough; the rest of a fast run is held
    slots = []
    for k, r in enumerate(rows):
        dur = r["end"] - r["t"]
        after_gap = k == 0 or r["t"] - rows[k - 1]["end"] > 0.1
        next_dur = (rows[k + 1]["end"] - rows[k + 1]["t"]) if k + 1 < len(rows) else 0.0
        leads_into_long = dur < a.min_syllable_s and next_dur >= 2 * a.min_syllable_s and (k == 0 or (rows[k - 1]["end"] - rows[k - 1]["t"]) >= a.min_syllable_s)
        slots.append(after_gap or dur >= a.min_syllable_s or leads_into_long)   # a lone short note before a long one is a pickup syllable, not a run
    runs = sum(1 for k in range(1, len(rows)) if not slots[k])
    report.append(f"{len(sylls)} syllables in {len(lines)} line(s); {len(rows)} notes ({sum(1 for r in rows if r['placed']=='interpolated')} placed by interpolation); "
                  f"{sum(slots)} can carry a syllable, {runs} are fast-run notes held on the previous vowel (shorter than {a.min_syllable_s}s)")
    # phrases: a new one starts after a long hold or pause; each lyric line goes on the next phrase
    phrases, cur = [], [0]
    for k in range(1, len(rows)):
        if rows[k]["t"] - rows[k - 1]["t"] >= a.phrase_gap_s:
            phrases.append(cur); cur = []
        cur.append(k)
    phrases.append(cur)
    line_sylls = []
    for ln in lines:
        ls = []
        for word in re.findall(r"[A-Za-z']+", ln):
            ph = syllabify(word, g2p); texts = split_text(word, len(ph))
            ls += [{"word": word, "text": tx, "phoneme": "en_" + "-".join(p), "line": ln} for tx, p in zip(texts, ph)]
        line_sylls.append(ls)
    report.append(f"{len(phrases)} musical phrase(s) in the melody (split at holds or pauses of {a.phrase_gap_s}s or more): " +
                  "; ".join(f"notes {ph[0]}–{ph[-1]} ({rows[ph[0]]['t']:.1f}s, {sum(1 for k in ph if slots[k])} syllable slots)" for ph in phrases))
    out = [None] * len(rows)
    for pi, ph in enumerate(phrases):
        ls = line_sylls[pi] if pi < len(line_sylls) else []
        si = 0
        for k in ph:
            r = rows[k]
            prev = out[k - 1] if k > 0 and out[k - 1] else None
            if not slots[k] and prev and prev["kind"] != "unsung":
                out[k] = {**r, "text": "~", "phoneme": prev["phoneme"], "kind": "slur", "word": prev["word"]}
            elif si < len(ls):
                sy = ls[si]; si += 1
                out[k] = {**r, "text": sy["text"], "phoneme": sy["phoneme"], "kind": "note", "word": sy["word"]}
            elif prev and prev["kind"] != "unsung" and r["t"] - rows[k - 1]["end"] <= 1.0:
                out[k] = {**r, "text": "~", "phoneme": prev["phoneme"], "kind": "slur", "word": prev["word"]}
                report.append(f"phrase {pi+1}: note {k} ({r['t']}s) has no syllable left; it holds '{prev['word']}'")
            else:
                out[k] = {**r, "text": "", "phoneme": "", "kind": "unsung", "word": None}
                report.append(f"phrase {pi+1}: note {k} ({r['t']}s) has no syllable left and nothing to hold; left unsung — say if it should carry a word")
        if si < len(ls):
            left = " ".join(x["text"] for x in ls[si:])
            report.append(f"phrase {pi+1} (line {pi+1}: '{lines[pi]}'): {len(ls) - si} syllable(s) did not fit on its {sum(1 for k in ph if slots[k])} slot(s) and were left out: '{left}' — shorten the line, or say which word to drop")
    if len(line_sylls) > len(phrases):
        report.append(f"{len(line_sylls) - len(phrases)} line(s) have no phrase to go on and were left out: " + " / ".join(lines[len(phrases):]))
    out = [x for x in out if x]
    json.dump({"melody": a.melody, "lyrics": str(a.lyrics), "lines": lines, "transpose": a.transpose, "rows": out, "report": report}, open(a.out, "w"), indent=1, ensure_ascii=False)
    for r in report:
        print("FIT:", r)
    print(" ".join(f"{r['text']}" for r in out))


if __name__ == "__main__":
    main()
