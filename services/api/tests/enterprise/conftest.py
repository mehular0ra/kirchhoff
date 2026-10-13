from pathlib import Path

import pytest

from kirchhoff.contracts import Material, Opportunity, PRLine, PurchaseRequisition
from kirchhoff.enterprise.model import EnterpriseSeed
from kirchhoff.enterprise.sandbox import Sandbox
from kirchhoff.store.memory import MemoryStore

REPO = Path(__file__).resolve().parents[4]
SCENARIOS = REPO / "scenarios"


def mat(mid: str, category: str = "transformer", stock: int = 6, lead: int = 12, price: float = 100.0,
        vendor: str = "Tapti Transformers", voltage: str | None = "33/0.415 kV") -> Material:
    return Material(id=mid, category=category, description=f"{mid} item", rating=1.0, unit="ea", voltage=voltage,
                    stock=stock, lead_time_weeks=lead, unit_price=price, vendor=vendor)


class Clock:
    def __init__(self, t: float = 1792200000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


@pytest.fixture
def small_seed() -> EnterpriseSeed:
    return EnterpriseSeed(
        materials=[mat("TX-3150"), mat("TX-2500", stock=0, lead=98),
                   mat("BW-1600", category="busway", stock=900, lead=8, vendor="Indus Busbar Systems", voltage="415 V")],
        prs=[PurchaseRequisition(id="PR-2026-0142", project_id="hall-a", revision="r2",
                                 lines=[PRLine(material_id="TX-3150", description="TX-3150 item", qty=6,
                                               unit_price=100.0, lead_time_weeks=12)],
                                 status="submitted", created_at=1791800000.0)],
        accounts=["Deccan Compute"],
        opportunities=[
            Opportunity(id="opp-hall-a", account="Deccan Compute", name="Hall A design-build", stage="Design approved",
                        value=18500000.0, next_step="Issue purchase requisitions"),
            Opportunity(id="opp-hall-b", account="Deccan Compute", name="Hall B design-build",
                        stage="Design in progress", value=18500000.0, next_step="Run the Hall B design"),
        ])


@pytest.fixture
def sandbox(small_seed) -> Sandbox:
    sb = Sandbox(MemoryStore(), clock=Clock())
    sb.load_seed(small_seed)
    return sb
