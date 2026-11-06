#!/usr/bin/env python3
"""clock.py — the ONE conversion between bar:beat and seconds in the ARRANGE pipeline.

    python3 clock.py check piano-analysis.json              # refuses bad maps, lists uncertain bars
    python3 clock.py t     piano-analysis.json 17 1          # seconds of bar 17 beat 1
    python3 clock.py bar   piano-analysis.json 74.1          # bar:beat at 74.1 s
    python3 clock.py table piano-analysis.json               # bar -> downbeat seconds, local bpm

Reads `tempo_map.beats` ([{t, bar, beat}, ...]) and nothing else. The map is
MEASURED by /arrange-listen (or tapped/confirmed by the creator); this script
never estimates, smooths or fills gaps.

Rules:

- A position is (bar, beat) with 1 <= beat < beats_per_bar + 1. Beat 4.5 in
  4/4 is fine; beat 5 is refused. Non-finite values are refused.
- The map's domain runs from its first beat to the END of its last beat
  (one beat past the last entry, at the last measured beat duration). That
  end point is the exclusive boundary used for "through bar N" exits and is
  flagged `boundary`.
- Anything outside the domain is refused unless the caller passes
  extrapolate=True, and is then flagged `extrapolated`, in both directions.
- Intervals are half-open: a layer that sounds "through bar 40" exits at
  (41, 1), the start of bar 41, never at (40, 4).
- Duplicate (bar, beat) entries, out-of-meter entries and non-increasing
  times make the map unusable; check() lists them.

Importable: `from clock import Clock, ClockError`.
"""
import argparse, json, math, sys
from pathlib import Path


class ClockError(Exception):
    pass


class Clock:
    def __init__(self, analysis: dict):
        tm = analysis.get("tempo_map") or {}
        beats = tm.get("beats") or []
        if len(beats) < 2:
            raise ClockError("tempo_map.beats has fewer than two beats — /arrange-listen must measure the map first")
        self.ts = tm.get("time_signature", "4/4")
        try:
            self.bpb = int(self.ts.split("/")[0])
        except (ValueError, AttributeError):
            raise ClockError(f"time signature {self.ts!r} is not n/d")
        if self.bpb < 1:
            raise ClockError(f"time signature {self.ts!r} has no beats")
        cleaned = []
        for b in beats:
            try:
                t, bar, beat = float(b["t"]), int(b["bar"]), int(b["beat"])
            except (KeyError, TypeError, ValueError):
                raise ClockError(f"malformed beat entry {b!r}")
            if not math.isfinite(t):
                raise ClockError(f"non-finite time at bar {bar}:{beat}")
            if b["beat"] != beat:
                raise ClockError(f"beat entries must be whole beats, got {b['beat']!r} at bar {bar}")
            if not 1 <= beat <= self.bpb:
                raise ClockError(f"bar {bar}:{beat} is outside {self.ts}")
            cleaned.append({"t": t, "bar": bar, "beat": beat})
        self.beats = sorted(cleaned, key=lambda b: b["t"])
        self.unresolved = tm.get("unresolved", [])
        self.index = {}
        for b in self.beats:
            key = (b["bar"], b["beat"])
            if key in self.index:
                raise ClockError(f"duplicate entry for bar {b['bar']}:{b['beat']}")
            self.index[key] = b["t"]
        self.first = (self.beats[0]["bar"], self.beats[0]["beat"])
        self.last = (self.beats[-1]["bar"], self.beats[-1]["beat"])
        self.last_dur = self.beats[-1]["t"] - self.beats[-2]["t"]
        self.first_dur = self.beats[1]["t"] - self.beats[0]["t"]

    # ---- positions ---------------------------------------------------------
    def _ordinal(self, bar: int, beat: float) -> float:
        """Beats since the map's first beat (fractional)."""
        return (bar - self.first[0]) * self.bpb + (beat - self.first[1])

    def _position(self, ordinal: float):
        """Inverse of _ordinal: (bar, beat) with 1 <= beat < bpb + 1."""
        whole = math.floor(ordinal + 1e-9)
        frac = ordinal - whole
        if abs(frac) < 1e-9:
            frac = 0.0
        total = (self.first[1] - 1) + whole
        bar = self.first[0] + total // self.bpb
        beat = total % self.bpb + 1 + frac
        return bar, beat

    def validate_position(self, bar, beat):
        try:
            bar, beat = int(bar), float(beat)
        except (TypeError, ValueError):
            raise ClockError(f"position {bar!r}:{beat!r} is not bar:beat")
        if not math.isfinite(beat):
            raise ClockError(f"beat {beat!r} is not finite")
        if not 1.0 <= beat < self.bpb + 1:
            raise ClockError(f"beat {beat:g} is outside {self.ts} (beats run 1 to {self.bpb})")
        return bar, beat

    def flags_for(self, bar, beat):
        """'interior' | 'boundary' (the end of the last beat) | 'extrapolated' | 'before'."""
        o = self._ordinal(bar, beat)
        n = len(self.beats) - 1  # ordinal of the last entry
        if o < -1e-9:
            return "before"
        if o <= n + 1e-9:
            return "interior"
        if o <= n + 1 + 1e-9:
            return "boundary"
        return "extrapolated"

    # ---- conversions ------------------------------------------------------
    def t(self, bar: int, beat: float = 1.0, *, extrapolate: bool = False):
        """Seconds for a (possibly fractional) position. Returns (seconds, flags)."""
        bar, beat = self.validate_position(bar, beat)
        where = self.flags_for(bar, beat)
        o = self._ordinal(bar, beat)
        n = len(self.beats) - 1
        if where == "interior":
            k = min(int(math.floor(o + 1e-9)), n)
            frac = o - k
            t0 = self.beats[k]["t"]
            if frac <= 1e-9:
                return t0, []
            return t0 + frac * (self.beats[k + 1]["t"] - t0), []
        if where == "boundary":
            return self.beats[-1]["t"] + (o - n) * self.last_dur, ["boundary"]
        if not extrapolate:
            side = "before the first beat" if where == "before" else "past the end of the map"
            raise ClockError(f"bar {bar}:{beat:g} is {side} ({self.first[0]}:{self.first[1]} to end of {self.last[0]}:{self.last[1]}); pass extrapolate=True to allow it")
        if where == "before":
            return self.beats[0]["t"] + o * self.first_dur, ["extrapolated"]
        return self.beats[-1]["t"] + (o - n) * self.last_dur, ["extrapolated"]

    def bar_end(self, bar: int, *, extrapolate: bool = False):
        """Seconds at the END of a bar = start of the next bar's beat 1 (half-open exit)."""
        return self.t(bar + 1, 1, extrapolate=extrapolate)

    def end(self):
        """The exclusive end of the map: one beat past the last entry. Returns (seconds, (bar, beat))."""
        o = len(self.beats)  # n + 1
        return self.beats[-1]["t"] + self.last_dur, self._position(o)

    def at(self, seconds: float, *, extrapolate: bool = False):
        """(bar, beat_float) at a time. Refuses times outside the domain unless extrapolate=True."""
        seconds = float(seconds)
        if not math.isfinite(seconds):
            raise ClockError(f"time {seconds!r} is not finite")
        first_t, last_t = self.beats[0]["t"], self.beats[-1]["t"]
        if seconds < first_t - 1e-9:
            if not extrapolate:
                raise ClockError(f"{seconds:.3f}s is before the first beat at {first_t:.3f}s; pass extrapolate=True to allow it")
            return self._position((seconds - first_t) / self.first_dur)
        if seconds >= last_t - 1e-9:
            o = (len(self.beats) - 1) + (seconds - last_t) / self.last_dur
            if o > len(self.beats) + 1e-9 and not extrapolate:
                end_t, end_pos = self.end()
                raise ClockError(f"{seconds:.3f}s is past the end of the map at {end_t:.3f}s (= {end_pos[0]}:{end_pos[1]:g}); pass extrapolate=True to allow it")
            return self._position(o)
        lo, hi = 0, len(self.beats) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.beats[mid]["t"] <= seconds:
                lo = mid
            else:
                hi = mid
        b1, b2 = self.beats[lo], self.beats[hi]
        frac = (seconds - b1["t"]) / (b2["t"] - b1["t"])
        return self._position(lo + frac)

    # ---- validation -------------------------------------------------------
    def check(self):
        """Return a list of problems; empty means the map is usable."""
        problems, prev = [], None
        durs = [b2["t"] - b1["t"] for b1, b2 in zip(self.beats, self.beats[1:])]
        typical = sorted(durs)[len(durs) // 2] if durs else 0
        for b in self.beats:
            if prev is not None:
                exp_bar, exp_beat = prev["bar"], prev["beat"] + 1
                if exp_beat > self.bpb:
                    exp_bar, exp_beat = exp_bar + 1, 1
                if (b["bar"], b["beat"]) != (exp_bar, exp_beat):
                    problems.append(f"bar numbering jumps from {prev['bar']}:{prev['beat']} to {b['bar']}:{b['beat']}")
                gap = b["t"] - prev["t"]
                if gap <= 0:
                    problems.append(f"non-increasing time at bar {b['bar']}:{b['beat']}")
                elif typical and gap > 2.0 * typical:
                    problems.append(f"gap of {gap:.2f}s before bar {b['bar']}:{b['beat']} (typical beat {typical:.2f}s) — fermata or missing beats?")
            prev = b
        return problems

    def table(self):
        rows, downbeats = [], [b for b in self.beats if b["beat"] == 1]
        for d1, d2 in zip(downbeats, downbeats[1:]):
            rows.append({"bar": d1["bar"], "t": d1["t"], "bpm": 60.0 * self.bpb / (d2["t"] - d1["t"])})
        if downbeats:
            rows.append({"bar": downbeats[-1]["bar"], "t": downbeats[-1]["t"], "bpm": None})
        return rows

    def uncertain_bars(self):
        """Bar numbers mentioned in tempo_map.unresolved (best-effort text scan)."""
        import re
        bars = set()
        for s in self.unresolved:
            for m in re.finditer(r"bars?\s*(\d+)(?:\s*[–\-]\s*(\d+))?", s):
                a, b = int(m.group(1)), int(m.group(2) or m.group(1))
                bars.update(range(a, b + 1))
        return sorted(bars)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "t", "bar", "table"])
    ap.add_argument("analysis")
    ap.add_argument("args", nargs="*")
    ap.add_argument("--extrapolate", action="store_true")
    a = ap.parse_args()
    try:
        clk = Clock(json.loads(Path(a.analysis).read_text()))
    except ClockError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        if a.cmd == "check":
            probs = clk.check()
            for p in probs:
                print(f"GAP: {p}")
            ub = clk.uncertain_bars()
            if ub:
                print(f"UNCERTAIN bars (from /arrange-listen): {ub}")
            end_t, end_pos = clk.end()
            print(f"domain: {clk.first[0]}:{clk.first[1]} at {clk.beats[0]['t']:.3f}s to end of {clk.last[0]}:{clk.last[1]} at {end_t:.3f}s (= {end_pos[0]}:{end_pos[1]:g})")
            print("OK — map usable" if not probs else f"REFUSED — {len(probs)} problem(s)")
            sys.exit(0 if not probs else 1)
        if a.cmd == "t":
            bar, beat = int(a.args[0]), float(a.args[1]) if len(a.args) > 1 else 1.0
            s, flags = clk.t(bar, beat, extrapolate=a.extrapolate)
            print(f"{s:.3f}" + (f"  ({', '.join(flags)})" if flags else ""))
        elif a.cmd == "bar":
            bar, beat = clk.at(float(a.args[0]), extrapolate=a.extrapolate)
            print(f"{bar}:{beat:.2f}")
        elif a.cmd == "table":
            for r in clk.table():
                bpm = f"{r['bpm']:.1f}" if r["bpm"] else "—"
                print(f"bar {r['bar']:>3}  {r['t']:8.3f}s  {bpm:>6} bpm")
    except ClockError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
