import shutil, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"


@pytest.fixture
def copy_of(tmp_path):
    """A copy of an experiment folder (with the skills beside it), so scripts that write tables leave the repo alone."""
    def make(name):
        (tmp_path / "experiments").mkdir(exist_ok=True)
        for sub in ("revisions", "corrections", name):
            dst = tmp_path / "experiments" / sub
            if not dst.exists():
                shutil.copytree(EXP / sub, dst, ignore=shutil.ignore_patterns("__pycache__", "cache"))
        if not (tmp_path / "skills").exists():
            shutil.copytree(ROOT / "skills", tmp_path / "skills", ignore=shutil.ignore_patterns("__pycache__"))
        return tmp_path / "experiments" / name
    return make


def run(folder, *args):
    r = subprocess.run([sys.executable, *args], cwd=folder, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout
