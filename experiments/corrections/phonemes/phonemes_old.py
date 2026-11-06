#!/usr/bin/env python3
"""phonemes.py — phonemes for every sung row of a fit, split by syllable across a word's notes (/arrange-lyrics; needs g2p_en).

    python phonemes.py fit.json score.json [--legato]

Drops unsung rows (they are the piano's), gives each held row (~) the phoneme
of the note it holds, and splits a word's ARPAbet phones at its vowels across
the notes that carry its syllables. With --legato a sung note is held through
a gap of under 1.6 s to the next sung note (grey notes in between are the
piano's), so the singer does not stop and restart.
"""
import json, re, sys
legato = '--legato' in sys.argv
sys.argv = [x for x in sys.argv if x != '--legato']
# --legato-max S: hold through gaps shorter than S seconds only (default 1.6); a smaller value keeps the composer's breaths
legato_max = 1.6
if '--legato-max' in sys.argv:
    i = sys.argv.index('--legato-max'); legato_max = float(sys.argv[i + 1]); del sys.argv[i:i + 2]
# --pronounce file.json: {"Footsteps": ["F UH", "T S T EH P S"]} — the composer's own split of a word's sounds across its notes
pron = {}
if '--pronounce' in sys.argv:
    i = sys.argv.index('--pronounce'); pron = {k.lower(): v for k, v in json.load(open(sys.argv[i + 1])).items()}; del sys.argv[i:i + 2]
from g2p_en import G2p

# consonants between two vowels go to the next syllable only as far as English lets a syllable
# begin with them: mor|ning (not mo|rning, which a singer voices as "mo-re-ning"), foot|steps, a|cross
_C2 = {("S", c) for c in ("P", "T", "K", "M", "N", "L", "W", "F")} | {(c, "R") for c in ("P", "B", "T", "D", "K", "G", "F", "TH", "SH")} \
    | {(c, "L") for c in ("P", "B", "K", "G", "F", "S")} | {(c, "W") for c in ("T", "D", "K", "G", "S", "TH")} \
    | {(c, "Y") for c in ("P", "B", "T", "D", "K", "G", "F", "V", "M", "N", "HH", "L", "S")}
_C3 = {("S", "P", "R"), ("S", "T", "R"), ("S", "K", "R"), ("S", "P", "L"), ("S", "K", "W"), ("S", "P", "Y"), ("S", "K", "Y")}


def legal_onset(cl):
    return len(cl) == 0 or (len(cl) == 1 and cl[0] != "NG") or (len(cl) == 2 and tuple(cl) in _C2) or (len(cl) == 3 and tuple(cl) in _C3)


def onset_cut(ph, v1, v2):
    """Where to cut between the vowels at v1 and v2: the longest legal onset goes with the second."""
    for start in range(v1 + 1, v2 + 1):
        if legal_onset(ph[start:v2]):
            return start
    return v2
g=G2p(); src, dst = sys.argv[1], sys.argv[2]
d=json.load(open(src)); rows=[r for r in d['rows'] if r['kind']!='unsung']
i=0
while i < len(rows):
    r=rows[i]
    if r['kind']=='slur': r['phoneme']=rows[i-1]['phoneme'] if i else ''; i+=1; continue
    w=r['word']; grp=[i]; holds=[]; j=i+1
    # the word's later syllables; a held note (slur) between two of them stays with the syllable before it (a-~-lone)
    while j < len(rows):
        x=rows[j]
        if x['kind']=='note' and x['word']==w and x['text']!=w: grp.append(j); j+=1; continue
        if x['kind']=='slur' and x.get('word')==w and j+1<len(rows) and rows[j+1]['kind']=='note' and rows[j+1]['word']==w and rows[j+1]['text']!=w: holds.append(j); j+=1; continue
        break
    ph=[p for p in g(w) if re.fullmatch(r'[A-Z]+[012]?', p)]; vow=[k for k,p in enumerate(ph) if re.match(r'[AEIOU]',p)]
    if w.lower() in pron and len(pron[w.lower()])==len(grp):
        # a vowel without a stress digit gets 1 on the word's first vowel, 0 after (the phone set wants a digit)
        seen=[0]
        def stress(x):
            if re.match(r'[AEIOU]',x) and not re.search(r'\d$',x): x+= '1' if not seen[0] else '0'; seen[0]=1
            return x
        for k,gi in enumerate(grp): rows[gi]['phoneme']='en_'+'-'.join(stress(x) for x in pron[w.lower()][k].split())
    elif len(grp)==1 or len(vow)<len(grp):
        rows[grp[0]]['phoneme']='en_'+'-'.join(ph)
        for k in grp[1:]: rows[k]['phoneme']=rows[grp[0]]['phoneme']; rows[k]['kind']='slur'; rows[k]['text']='~'
    else:
        cuts=[0]+[vow[j]+1 for j in range(len(grp)-1)]+[len(ph)]
        for k,gi in enumerate(grp): rows[gi]['phoneme']='en_'+'-'.join(ph[cuts[k]:cuts[k+1]])
    for h in holds: rows[h]['phoneme']=rows[h-1]['phoneme']
    i=max(grp+holds)+1
for k,r in enumerate(rows): r['index']=k
if legato:
    for a, b in zip(rows, rows[1:]):
        if 0 < b['t'] - a['end'] < legato_max:
            a['end'] = b['t']
d['rows']=rows; json.dump(d, open(dst,'w'), indent=1, ensure_ascii=False); print(len(rows), 'sung rows with phonemes' + (' (legato)' if legato else ''))
