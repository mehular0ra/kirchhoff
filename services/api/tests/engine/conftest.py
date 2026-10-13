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
