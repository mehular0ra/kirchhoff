from pathlib import Path

import pytest

from kirchhoff.enterprise.world.inbox import InboxSeed, load_inbox_seed

REPO = Path(__file__).resolve().parents[4]
SCENARIOS = REPO / "scenarios"
AS_OF = 1792132200.0  # world anchor: 2026-10-16 12:00 IST


@pytest.fixture(scope="session")
def scenarios() -> Path:
    return SCENARIOS


@pytest.fixture(scope="session")
def inbox_seed() -> InboxSeed:
    """I-1's committed seed (scenarios/demo_world/out/inbox_seed.json) with its rendered attachments."""
    return load_inbox_seed(SCENARIOS / "demo_world" / "out" / "inbox_seed.json")


@pytest.fixture(scope="session")
def erp():
    from kirchhoff.engine.api import default_erp
    return default_erp()  # the Hall A ERP: TX-2500 0 in stock / 98 weeks, TX-3150 6 in stock
