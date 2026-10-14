"""Normal and N-1 load study (spec §8.2 Redundancy): a networkx graph of the distribution; on loss of any
component, affected feeds transfer to each rack's other feed. No repeated load flows."""
from collections import defaultdict
from dataclasses import dataclass

import networkx as nx

from kirchhoff.contracts import DesignModel

from . import calc
from .scenario import Scenario, limit

CHAIN_KINDS = ("transformer", "lv_board", "ups", "critical_board")


@dataclass
class Case:
    id: str  # "normal" or "loss:<component>"
    failed: str | None
    failed_system: str | None
    busway_a: dict[str, float]
    busway_kw: dict[str, float]
    system_it_kw: dict[str, float]
    system_aux_kw: dict[str, float]
    system_kva: dict[str, float]
    ups_kw: dict[str, float]
    unfed: list[str]


@dataclass
class Study:
    normal: Case
    cases: list[Case]  # one per N-1 component loss
    busway_system: dict[str, str]
    feeder_of: dict[str, str]  # busway id -> feeder connection id
    systems: list[str]
    spofs: list[str]

    def worst_busway_a(self, busway_id: str) -> float:
        return max(c.busway_a.get(busway_id, 0.0) for c in [self.normal, *self.cases])

    def kva_normal(self, system: str) -> float:
        return self.normal.system_kva.get(system, 0.0)

    def kva_n1(self, system: str) -> float:
        return max((c.system_kva.get(system, 0.0) for c in self.cases), default=0.0)

    def ups_kw_max(self, system: str) -> float:
        return max(c.ups_kw.get(system, 0.0) for c in [self.normal, *self.cases])


def build_graph(model: DesignModel) -> nx.DiGraph:
    """Equipment ids are nodes; feeders (busway/cable connections) are nodes too, so they can fail."""
    g = nx.DiGraph()
    g.add_nodes_from(e.id for e in model.equipment)
    for c in model.connections:
        if c.kind == "internal":
            g.add_edge(c.src, c.dst)
        else:
            g.add_edge(c.src, c.id)
            g.add_edge(c.id, c.dst)
    return g


def study(scn: Scenario, model: DesignModel) -> Study:
    u, pf = limit(scn, "lv_v"), limit(scn, "pf")
    eq = {e.id: e for e in model.equipment}
    g = build_graph(model)
    busways = sorted(e.id for e in model.equipment if e.kind == "busway")
    chain = {b: (nx.ancestors(g, b) | {b}) - {"MV"} for b in busways}
    busway_system = {}
    for b in busways:
        boards = sorted(n for n in chain[b] if n in eq and eq[n].kind == "critical_board")
        busway_system[b] = eq[boards[0]].system if boards else ""
    feeder_of = {c.dst: c.id for c in model.connections if c.kind in ("busway", "cable") and c.dst in eq
                 and eq[c.dst].kind == "busway"}
    systems = sorted({e.system for e in model.equipment if e.kind in CHAIN_KINDS and e.system})
    eta = {e.system: float(e.params.get("eta", 0.97)) for e in model.equipment if e.kind == "ups"}
    aux_total = float(model.loads.get("aux_mw", 0.0)) * 1000.0
    ups_frac = float(model.loads.get("pumps_kw", 0.0)) / aux_total if aux_total else 0.0

    def allocate(alive: set[str]):
        busway_kw: dict[str, float] = defaultdict(float)
        busway_a: dict[str, float] = defaultdict(float)
        unfed = []
        for r in model.racks:
            fa, fb = r.feeds
            ok_a, ok_b = fa in alive, fb in alive
            if model.topology == "BLOCK":
                shares = [(fa, 1.0)] if ok_a else ([(fb, 1.0)] if ok_b else [])
            elif ok_a and ok_b:
                shares = [(fa, 0.5), (fb, 0.5)]
            else:
                shares = [(fa, 1.0)] if ok_a else ([(fb, 1.0)] if ok_b else [])
            if not shares:
                unfed.append(r.id)
            i_rack = calc.design_current_a(r.kw, u, pf)
            for b, share in shares:
                busway_kw[b] += share * r.kw
                busway_a[b] += share * i_rack
        it = {s: 0.0 for s in systems}
        for b, kw in busway_kw.items():
            it[busway_system[b]] = it.get(busway_system[b], 0.0) + kw
        return dict(busway_a), dict(busway_kw), it, unfed

    def finish(cid, failed, failed_system, alloc, aux):
        busway_a, busway_kw, it, unfed = alloc
        kva = {s: calc.transformer_kva(it[s], aux[s] * ups_frac, aux[s] * (1 - ups_frac), eta.get(s, 0.97), pf)
               if (it[s] > 0 or aux[s] > 0) else 0.0 for s in systems}
        ups = {s: it[s] + aux[s] * ups_frac for s in systems}
        return Case(cid, failed, failed_system, busway_a, busway_kw, it, aux, kva, ups, unfed)

    normal_alloc = allocate(set(busways))
    it_normal = normal_alloc[2]
    carrying = [s for s in systems if it_normal[s] > 0]
    aux_normal = {s: (aux_total / len(carrying) if s in carrying else 0.0) for s in systems}
    normal = finish("normal", None, None, normal_alloc, aux_normal)

    components = sorted([e.id for e in model.equipment if e.kind in (*CHAIN_KINDS, "sts", "busway")]
                        + list(feeder_of.values()))
    cases, spofs = [], []
    for comp in components:
        alive = {b for b in busways if comp not in chain[b]}
        alloc = allocate(alive)
        failed_system = eq[comp].system if comp in eq and eq[comp].kind in CHAIN_KINDS else None
        aux = dict(aux_normal)
        if failed_system:
            moved = aux.get(failed_system, 0.0)
            aux[failed_system] = 0.0
            deltas = {s: max(0.0, alloc[2][s] - it_normal[s]) for s in systems if s != failed_system}
            total = sum(deltas.values())
            if total > 0:
                for s, d in deltas.items():
                    aux[s] += moved * d / total
        case = finish(f"loss:{comp}", comp, failed_system, alloc, aux)
        if case.unfed:
            spofs.append(comp)
        cases.append(case)
    return Study(normal, cases, busway_system, feeder_of, systems, spofs)
