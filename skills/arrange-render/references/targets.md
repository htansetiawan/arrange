# Export target: Logic Pro (stems + tempo/marker MIDI + import notes)

`scripts/export.py` writes a folder Logic Pro (or any DAW that imports audio
files and a Standard MIDI File) can open. Logic has no documented, writable
project format, so the export leans on the two imports Logic does reliably:

1. **Audio files dragged to bar 1.** Every stem is full-length and
   zero-aligned, so no positional data needs to survive an importer. This is
   the load-bearing decision.
2. **Standard MIDI File import** (File ▸ Import ▸ MIDI File). Logic reads the
   file's tempo events into the tempo track when asked, time-signature events,
   and marker meta-events into the marker track. `scripts/smf.py` writes a
   type-1 SMF: track 0 = a pre-roll bar, then the tempo map (one tempo event per
   measured beat), the time signature and section markers named from
   `sections`; further tracks = the transcribed piano (`--midi`) and note
   tracks. Stdlib only.

Folder written:

```
export/logic/
  stems/00_piano.wav  01_vocal.wav  02_strings.wav  03_guitar_STUB.wav ...
  tempo-markers.mid
  IMPORT.md            # the steps below, with this project's rate and names filled in
  arrangement.json  piano-analysis.json   # copies
  render-report.json   # what was exported: stems, frame checks, the MIDI origin
```

`IMPORT.md` says: (1) new empty project at the export rate; (2) File ▸ Import ▸
MIDI File → `tempo-markers.mid`, say yes to importing the tempo; (3) drag all
stems onto the tracks area at bar 1, one new track per file. Stubs are the
empty tracks whose names end in `_STUB`.

## Why the tempo map matters in Logic even though the stems don't need it

With the map imported, Logic's bar lines follow the performance, so the
creator can cut, quantise and add MIDI parts against a grid that matches the
rubato, derived from the same measurements as every other number in ARRANGE.
The first measured downbeat sits some way into the recording; `smf.py` puts a
pre-roll bar before it and the stems are padded to match (see its docstring).

## Parity

Before writing, `export.py` checks that every layer in `arrangement.json`
(in `order`) maps to exactly one stem: a generated layer needs a chosen
rendered candidate, a take needs its file, a stub is written as silence. Any
miss aborts the export with the layer named.
