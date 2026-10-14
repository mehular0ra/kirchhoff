import os
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kirchhoff.agents.ports import EnterpriseClient, ErpSnapshot
from kirchhoff.agents.runner import AgentRunner
from kirchhoff.store import Store

from .blobs import BlobStore


@dataclass(frozen=True)
class InputFiles:
    tender_pdf: Path
    plan_pdf: Path
    dxf: Path
    ground_truth: Path


def thread_spawn(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True).start()


def _owner_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"


@dataclass
class Deps:
    store: Store
    engine: Any  # kirchhoff.engine.api module (or FakeEngine): the facade functions by name
    runner: AgentRunner
    enterprise: EnterpriseClient
    blobs: BlobStore
    scenarios_dir: Path
    seed_dir: Path
    voice_runner: AgentRunner | None = None
    exporter: Any = None  # kirchhoff.agents.docs_export.Exporter; None means StubExporter
    asset_engines: dict[str, Callable[[Path], dict]] = field(default_factory=dict)
    phases: dict[str, Callable] | None = None  # test override of the phase registry
    spawn: Callable[[Callable[[], None]], None] = thread_spawn
    clock: Callable[[], float] = time.time
    owner: str = field(default_factory=_owner_id)
    heartbeat_s: float = 15.0
    erp_ttl_s: float = 300.0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._scenario = None
        self._erp: ErpSnapshot | None = None
        self._erp_at = 0.0

    def scenario(self):
        with self._lock:
            if self._scenario is None:
                self._scenario = self.engine.load_scenario("hall_a", self.scenarios_dir)
            return self._scenario

    def erp(self) -> ErpSnapshot:
        with self._lock:
            now = time.monotonic()
            if self._erp is None or now - self._erp_at > self.erp_ttl_s:
                self._erp = ErpSnapshot(self.enterprise.list_materials())
                self._erp_at = now
            return self._erp

    def inputs(self) -> InputFiles:
        hall = Path(self.scenarios_dir) / "hall_a"
        return InputFiles(tender_pdf=hall / "out" / "tender-hall-a.pdf", plan_pdf=hall / "out" / "hall-a-plan.pdf",
                          dxf=hall / "out" / "hall-a.dxf", ground_truth=hall / "ground_truth.yaml")
