"""Clip voice -> voice stem: (path relative to the song project, audio suffix, semitone shift against the sung score,
or None where the shift is not in the file name and is inferred from the pitch)."""
SONG_RUN = {"all-the-things": "all-the-things-cohen", "color-purple": "color-purple", "someday": "someday-my-prince"}
_S = "build/studio/voice/"
STEMS = {
    "all-the-things": {"groban": (_S + "groban-12", "mp3", -12), "henry": (_S + "henry-yard-12", "mp3", -12),
                       "buble": ("build/key-8/voice/buble-8", "mp3", -8), "jackson": ("build/key-4/voice/jackson-4", "mp3", -4),
                       "wonder": ("build/key+1/voice/wonder+1", "mp3", 1), "ariana": ("build/key+2/voice/ariana+2", "mp3", 2),
                       "clarkson": ("build/key+2/voice/clarkson+2", "mp3", 2), "bolton": ("build/key-4/voice/bolton-4", "mp3", -4),
                       "adams": ("build/key-1/voice/adams-1", "mp3", -1)},
    "color-purple": {"groban": (_S + "groban-12", "mp3", -12), "own-score": ("build/public/voice/henry-yard-12", "mp3", -12),
                     "own-seedvc": ("build/seedvc/placed-stem2-C", "wav", None), "pavarotti": ("build/seedvc/placed-pavarotti-C", "wav", None),
                     "bolton": ("build/key+1/voice/bolton-11", "mp3", -11), "adams": ("build/key-6/voice/adams-6", "mp3", -6)},
    "someday": {"groban": (_S + "groban-12", "mp3", -12), "mine": (_S + "henry-yard-12", "mp3", -12),
                "ariana": ("build/key-2/voice/ariana-2", "mp3", -2), "clarkson": ("build/key+1/voice/clarkson+1", "mp3", 1),
                "bolton": ("build/key+1/voice/bolton-11", "mp3", -11), "adams": ("build/key+5/voice/adams-7", "mp3", -7)},
}
# window start of each song's mix in source time (make_clips.py SONGS)
WIN = {"all-the-things": 0, "color-purple": 0, "someday": 0}
# reference clip for likeness ($ARRANGE_RUNS/color-purple/voices/<name>/prompt); None = no reference
REF = {"henry": "henry-yard", "mine": "henry-yard", "own-score": "henry-yard", "own-seedvc": "henry-yard"}
