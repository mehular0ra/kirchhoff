"""Build the demo world (spec §13). This first version writes only the enterprise seed; Task 11 replaces it with the
full generator. Run from services/api:
  uv run python ../../scenarios/demo_world/build.py
"""
from pathlib import Path

from kirchhoff.enterprise.model import seed_hash
from kirchhoff.enterprise.world.config import load_world_config
from kirchhoff.enterprise.world.enterprise_data import build_enterprise_seed, build_materials, hall_a_materials

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    cfg = load_world_config(HERE / "world.yaml")
    seed = build_enterprise_seed(cfg, build_materials(cfg, hall_a_materials(HERE.parent)))
    out = HERE / "out" / "enterprise_seed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(seed.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"{out}: materials={len(seed.materials)} prs={len(seed.prs)} "
          f"opportunities={len(seed.opportunities)} hash={seed_hash(seed)}")
