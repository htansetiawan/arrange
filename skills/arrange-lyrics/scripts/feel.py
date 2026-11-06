"""feel.py — how the composer counts against the measured tempo map (/arrange-lyrics).

The beat tracker's map and the composer's count need not agree. Two numbers relate them,
read from the analysis's tempo_map:

- his_per_beat: the composer's beats per map beat (the field name is historical). 2 (the
  default) when the map tracks a slow half-time beat and the composer counts the fast one;
  1 when the map already tracks the composer's beat (for example a waltz).
- notated_time_signature: the bars the composer writes and reads. "4/4" by default; "3/4" for
  a waltz; "12/8" (or 6/8, 9/8) for a compound feel, where the beat is a dotted quarter split
  in three: bars then hold numerator/3 beats and notes snap to thirds of a beat.

The composer's beat b (0 = the map's first downbeat) is map ordinal b / his_per_beat; the
notated bar is b // beats_per_bar + 1.
"""


def compound(ts):
    n, d = (int(x) for x in ts.split("/"))
    return d == 8 and n % 3 == 0 and n > 3


def beats_per_bar(ts):
    n = int(ts.split("/")[0])
    return n // 3 if compound(ts) else n


def beat_ql(ts):
    """The composer's beat in quarter lengths: a dotted quarter in compound time, else one note of the denominator."""
    return 1.5 if compound(ts) else 4 / int(ts.split("/")[1])


def subdivision(ts):
    """Steps the composer's beat is snapped to: thirds (eighths) in compound time, quarters (sixteenths) otherwise."""
    return 3 if compound(ts) else 4


def feel(analysis):
    tm = analysis.get("tempo_map", analysis)
    per = int(tm.get("his_per_beat", 2))
    ts = tm.get("notated_time_signature", "4/4")
    return per, beats_per_bar(ts), ts
