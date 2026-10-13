import pytest


@pytest.fixture(scope="session")
def scn():
    from kirchhoff.engine.scenario import load_scenario

    return load_scenario("hall_a")


@pytest.fixture(scope="session")
def erp():
    from kirchhoff.engine.erp import default_erp

    return default_erp()


@pytest.fixture(scope="session")
def racks(scn):
    from kirchhoff.engine.layout import place_racks

    return place_racks(scn)


@pytest.fixture(scope="session")
def models(scn, racks):
    """Topology models before routing, keyed by (topology, transformer catalogue id)."""
    from kirchhoff.engine.topology import build_model

    return {(t, tx): build_model(scn, racks, t, tx) for t in ("2N", "DR", "BLOCK") for tx in ("TX-2500", "TX-3150")}
