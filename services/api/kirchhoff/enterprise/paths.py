"""Where scenario and demo files live: the repo checkout, or /app/scenarios and /app/seed in the image."""
import os
from pathlib import Path

_HERE = Path(__file__).resolve()


def repo_root() -> Path | None:
    for parent in _HERE.parents:
        if (parent / "scenarios").is_dir() and (parent / "services" / "api").is_dir():
            return parent
    return None


def scenarios_dir() -> Path:
    if os.environ.get("KIRCHHOFF_SCENARIOS_DIR"):
        return Path(os.environ["KIRCHHOFF_SCENARIOS_DIR"])
    for parent in _HERE.parents:
        if (parent / "scenarios" / "hall_a").is_dir():
            return parent / "scenarios"
    return Path("/app/scenarios")


def enterprise_seed_path() -> Path:
    return scenarios_dir() / "demo_world" / "out" / "enterprise_seed.json"
