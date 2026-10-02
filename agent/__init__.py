"""Loads ./.env on import (laptop dev). Existing environment variables always win,
so on the VM the team config is used untouched."""
import os
import pathlib

_env = pathlib.Path(__file__).resolve().parents[1] / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
