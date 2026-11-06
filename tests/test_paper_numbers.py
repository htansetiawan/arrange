"""The stored results reproduce the numbers in the paper. No model is called."""
from conftest import EXP, run


def test_revisions_tables_are_reproduced(copy_of):
    d = copy_of("revisions")
    run(d, "summarize.py", "results/summary.json", "-o", "results/SUMMARY.md")
    run(d, "table_models.py")
    run(d, "table_sessions.py")
    for f in ("results/SUMMARY.md", "results-models/TABLE.md", "sessions-results/TABLE.md"):
        assert (d / f).read_text() == (EXP / "revisions" / f).read_text(), f


def test_revisions_brass_turn(copy_of):
    out = run(copy_of("revisions"), "brass_turn.py", "sessions-results")
    assert "typed  failed (not turn_ok) 0/9" in out
    assert "patch  failed (not turn_ok) 9/9" in out


def test_canvas_edits_typed_against_raw_rows(copy_of):
    d = copy_of("canvas-edits")
    out = run(d, "suite.py", "--items")
    for line in ("claude-haiku-5-5 | 0.80", "+0.20 (26/6) | 0.000535", "claude-sonnet-5-5 | 0.91", "+0.17 (18/4) | 0.00434",
                 "claude-opus-5-5 | 0.92", "(12/4) | 0.0768", "gemma-4-31b-fp8 | 0.55", "(12/7)", "qwen3.5-27b-fp8 | 0.68", "(15/10)"):
        assert line in out, line
    assert out.count("| basic |") == 11


def test_canvas_edits_installed_skill(copy_of):
    out = run(copy_of("canvas-edits"), "skill_arm.py", "--table")
    for line in ("| claude-haiku-5-5 | 62 x 3 | 0.84 | 0.80 | 0.60 | 9/5", "| claude-opus-5-5 | 62 x 3 | 0.89 | 0.92 | 0.83 | 2/6",
                 "| claude-sonnet-5-5 | 62 x 3 | 0.82 | 0.91 | 0.74 | 2/12, p = 0.013", "186/186",
                 "| skill | 55/459 | 79/81 |", "| typed | 31/459 | 77/81 |", "| bare | 24/459 | 54/81 |"):
        assert line in out, line


def test_corrections(copy_of):
    out = run(copy_of("corrections"), "paper_numbers.py")
    for line in ("typed vs bare: 12 better, 6 worse", "free vs bare: 10 better, 3 worse",
                 "Claude  phoneme  typed 23/27  free 19/27  bare 0/27", "open    phoneme  typed 11/18  free 5/18  bare 0/18",
                 "gemma-4-31b-fp8      typed 1.37", "qwen3.5-27b-fp8      typed 2.00"):
        assert line in out, line


def test_voices(copy_of):
    out = run(copy_of("voices"), "paper_numbers.py")
    for s in ("SoulX 95.4, Seed-VC 90.0", "0.8 to 10.3", "better on 7, worse on 2 of 9", "22.8 (n = 9)",
              "113 clips, 518.8 s = 8.6 minutes", "0.876 -> 0.920", "largest |rho| 0.329"):
        assert s in out, s


def test_keys(copy_of):
    d = copy_of("keys")
    out = run(d, "paper_numbers.py")
    for s in ("mean miss 1.50, mean signed +0.00", "pilot 48, blind 60 + recheck 14, side by side 63: 185",
              "1.50, lean +0.00, exact 4 of 8, within 2 5 of 8", "8 of 8, one-sided p = 0.0039", "67.0 against 81.9",
              "Claude: with the numbers 1.6 to 1.8; by name 2.4 to 3.0"):
        assert s in out, s
    run(d, "make_fig3.py", "--print")
