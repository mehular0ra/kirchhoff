"""Build the demo world (spec §13): world.json, integrations.json, project bundles, documents, enterprise seed.
Deterministic (fixed seed and anchor). Run from services/api:
  uv run python ../../scenarios/demo_world/build.py            # write the files
  uv run python ../../scenarios/demo_world/build.py --check    # exit 1 if the committed files are stale
Captured runs in captures/{hall-a,pune-edge-1}.json (Task 14) take precedence over the engine-built bundles."""
import argparse
import importlib
import sys
from pathlib import Path

from kirchhoff.enterprise.capture import TARGETS, RawCapture
from kirchhoff.enterprise.world.build import build_world, diff_on_disk, write_world
from kirchhoff.enterprise.world.config import load_world_config

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the Kirchhoff demo world")
    ap.add_argument("--check", action="store_true", help="fail if the files on disk differ from a fresh build")
    args = ap.parse_args(argv)
    cfg = load_world_config(HERE / "world.yaml")
    try:
        engine = importlib.import_module("kirchhoff.engine.api")
    except ImportError:
        engine = None
        print("build: kirchhoff.engine.api is missing; building without engine projects", file=sys.stderr)
    captures = {pid: RawCapture.model_validate_json((HERE / "captures" / f"{pid}.json").read_text(encoding="utf-8"))
                for pid in sorted(TARGETS) if (HERE / "captures" / f"{pid}.json").exists()}
    if captures and engine is None:
        print("build: the captures need the engine", file=sys.stderr)
        return 1
    build = build_world(cfg, scenarios_root=ROOT / "scenarios", engine=engine, captures=captures)
    if build_world(cfg, scenarios_root=ROOT / "scenarios", engine=engine, captures=captures).digest() != build.digest():
        print("build: two builds differ; the generator is not deterministic", file=sys.stderr)
        return 1
    if args.check:
        stale = diff_on_disk(build, ROOT)
        if stale:
            print("stale demo-world files: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"demo world up to date ({build.digest()[:16]})")
        return 0
    written = write_world(build, ROOT)
    bundles = sorted(r.rsplit("/", 1)[1] for r in written if "/projects/" in r)
    print(f"demo world {build.digest()[:16]}: {len(written)} files; bundles {bundles}; captured {sorted(captures)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
