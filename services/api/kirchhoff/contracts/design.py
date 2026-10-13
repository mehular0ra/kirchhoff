from typing import Literal

from .common import Strict, TopologyId


class Point3(Strict):
    x: float
    y: float
    z: float


class Rack(Strict):
    id: str  # "R1-01"
    row: str  # "R1"
    x: float  # centre, metres
    y: float
    w: float = 0.6
    d: float = 1.2
    kw: float
    liquid_fraction: float
    feeds: tuple[str, str]  # (A busway id, B busway id)


EquipmentKind = Literal["mv_board", "transformer", "lv_board", "ups", "critical_board", "sts",
                        "busway", "rack_group"]


class Equipment(Strict):
    id: str  # "T-A1", "A1", "UPS-A1", "CB-A1", "A-01"
    kind: EquipmentKind
    rating: float | None = None
    unit: str | None = None  # "kVA", "A", "kW"
    catalogue_id: str | None = None
    system: str | None = None  # "A"/"B" (2N), "S1".."S4" (DR), "K1".."K3","KR" (BLOCK)
    room: str | None = None  # "A" | "B"
    params: dict[str, float | str] = {}


class Connection(Strict):
    id: str  # feeders "FA-01", internal links "L-T-A1-A1"
    src: str
    dst: str
    kind: Literal["cable", "busway", "internal"]
    length_m: float = 0.0
    catalogue_id: str | None = None
    route: list[Point3] = []


class CoolingNode(Strict):
    id: str  # "CDU-1", "M-R1"
    kind: Literal["cdu", "manifold"]
    zone: str  # "Z1".."Z3"
    capacity_kw: float | None = None
    x: float
    y: float


class Pipe(Strict):
    id: str  # "H-Z2", "BR-R3"
    kind: Literal["header", "branch"]
    zone: str
    dn: int
    tier: Literal["pipe_low", "pipe_high"]
    route: list[Point3]
    flow_lps: float = 0.0


class Geometry(Strict):
    hall: tuple[float, float]  # (60, 36)
    columns: list[tuple[float, float]]
    keepouts: list[tuple[float, float, float, float]]  # (x0, y0, x1, y1)
    rooms: dict[str, tuple[float, float, float, float]]
    tiers: dict[str, float]  # {"pipe_low": 2.6, "busway": 3.2, "pipe_high": 3.8}


class DesignModel(Strict):
    topology: TopologyId
    racks: list[Rack]
    equipment: list[Equipment]
    connections: list[Connection]
    cooling_nodes: list[CoolingNode]
    pipes: list[Pipe]
    geometry: Geometry
    loads: dict[str, float]  # rack_kw, liquid_fraction, aux_mw, pumps_kw
