#!/usr/bin/env python3
"""validate.py — mechanical checks of arrangement.json against the clock.

    python3 validate.py arrangement.json piano-analysis.json

Exit 0 when every check passes, 1 with the list otherwise. Checks: schema,
ids and order, anchors are valid positions inside the map, derived seconds
agree with the clock, exits after entries, routes and kinds agree, backends
support their class and only consume what they declare, audio context points
backward, stubs have reasons, takes have assets, chosen candidates exist.
Musical judgement is not checked here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arrangement as A  # noqa: E402


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    problems = A.validate(A.load(sys.argv[1]), A.load(sys.argv[2]))
    for p in problems:
        print("INVALID:", p)
    print("OK — plan is mechanically valid" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
