"""Shared configuration for the ARRANGE scripts: where the Python environments, the models and the voices live.

Settings come from a JSON file (config.example.json shows every key) and can be overridden by
environment variables. The file is $ARRANGE_CONFIG, else $XDG_CONFIG_HOME/arrange/config.json,
else ~/.config/arrange/config.json. A missing file is allowed: then only the environment
variables and the defaults below apply. docs/setup.md describes every setting.
"""
import json, os, sys
from pathlib import Path

_XDG = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
DEFAULT = Path(os.environ.get("ARRANGE_CONFIG") or _XDG / "arrange/config.json")

# setting (dotted key) -> environment variable that overrides it
ENV = {
    "python.analysis": "ARRANGE_PYTHON_ANALYSIS",
    "python.soulx": "ARRANGE_PYTHON_SOULX",
    "python.plain": "ARRANGE_PYTHON",
    "soulx.repo": "ARRANGE_SOULX_REPO",
    "soulx.checkpoint": "ARRANGE_SOULX_CHECKPOINT",
    "voices_dir": "ARRANGE_VOICES_DIR",
    "device": "ARRANGE_DEVICE",
    "whisper.model": "ARRANGE_WHISPER_MODEL",
    "whisper.cache": "ARRANGE_WHISPER_CACHE",
    "ace_step.repo": "ARRANGE_ACESTEP_REPO",
    "ace_step.checkpoints": "ARRANGE_ACESTEP_CHECKPOINTS",
    "ace_step.hf_home": "ARRANGE_HF_HOME",
    "ytdlp": "ARRANGE_YTDLP",
    "chrome": "ARRANGE_CHROME",
}

# used when neither the file nor the environment sets a value
DEFAULTS = {
    "python.analysis": sys.executable,
    "python.soulx": sys.executable,
    "python.plain": sys.executable,
    "device": "cuda",
    "whisper.model": "large-v3-turbo",
}


def _set(d, key, value):
    *head, last = key.split(".")
    for k in head:
        d = d.setdefault(k, {})
    d[last] = value


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flatten(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def get(cfg, key, default=None):
    """A dotted setting, e.g. get(cfg, "soulx.repo")."""
    d = cfg
    for k in key.split("."):
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def load(path=None):
    """The settings: defaults, then the config file (if it exists), then ARRANGE_* environment variables."""
    p = Path(path or DEFAULT)
    cfg = {}
    for k, v in DEFAULTS.items():
        _set(cfg, k, v)
    if p.exists():
        for k, v in _flatten(json.loads(p.read_text())).items():
            if not k.split(".")[-1].startswith("_"):
                _set(cfg, k, v)
    for k, var in ENV.items():
        if os.environ.get(var):
            _set(cfg, k, os.environ[var])
    return cfg


def require(cfg, key):
    """A setting that must be present; exits with a message naming the config key and its variable."""
    v = get(cfg, key)
    if v in (None, ""):
        raise SystemExit(f"ARRANGE setting '{key}' is not set: add it to {DEFAULT} (see config.example.json)"
                         + (f" or set {ENV[key]}" if key in ENV else ""))
    return v


def project(path):
    """A project file (arrange-project.json) with paths relative to its own folder."""
    p = Path(path).resolve(); d = json.loads(p.read_text()); base = p.parent
    def r(v):
        return str((base / v).resolve()) if isinstance(v, str) and v and not v.startswith("/") else v
    return {k: (r(v) if k not in ("title", "voice", "voice_label", "voice_shift", "window", "consent", "beat_offset", "version_label", "score_grid", "recorder_url") else v) for k, v in d.items()}, base
