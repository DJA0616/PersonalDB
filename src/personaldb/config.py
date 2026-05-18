"""
Configuration loader for PersonalDB.

Loads config/defaults.yaml first, then overlays config/local.yaml
if it exists. Values in local.yaml take precedence.

Usage:
    from personaldb.config import load_config
    cfg = load_config()
    model_name = cfg["models"]["embed"]
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


def _project_root() -> Path:
    """Return the project root directory (parent of src/)."""
    return Path(__file__).resolve().parent.parent.parent


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay into base. overlay values win."""
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    """Load merged configuration from defaults.yaml + optional local.yaml."""
    root = _project_root()
    defaults_path = root / "config" / "defaults.yaml"

    if not defaults_path.exists():
        print(f"Error: config/defaults.yaml not found at {defaults_path}", file=sys.stderr)
        sys.exit(1)

    with open(defaults_path, "r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)

    local_path = root / "config" / "local.yaml"
    if local_path.exists():
        with open(local_path, "r", encoding="utf-8") as fh:
            local = yaml.safe_load(fh)
            if local:
                config = _deep_merge(config, local)

    return config


# Module-level singleton for convenient import
_config: Dict[str, Any] | None = None


def get_config() -> Dict[str, Any]:
    """Return cached config, loading on first call."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
