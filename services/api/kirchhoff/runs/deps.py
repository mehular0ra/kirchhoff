import logging
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

log = logging.getLogger("kirchhoff.runs")
ERP_RETRY_S = 30.0  # after a failed refresh, keep serving the last snapshot this long before trying again


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
        self._lock = threading.Lock()  # the scenario only
        # P2 final fix wave (Important 4): the ERP refresh is an HTTP call (up to ~7 s with retries), so it has
        # its own lock; /api/what-if and voice, which need only the scenario, never wait behind it.
        self._erp_lock = threading.Lock()
        self._scenario = None
        self._erp: ErpSnapshot | None = None
        self._erp_at = 0.0
        self._erp_retry_at = 0.0  # after a failed refresh: no new attempt before this (monotonic) time

    def scenario(self):
        with self._lock:
            if self._scenario is None:
                self._scenario = self.engine.load_scenario("hall_a", self.scenarios_dir)
            return self._scenario

    def erp(self) -> ErpSnapshot:
        """The ERP catalogue, cached for `erp_ttl_s`. A failed refresh serves the last good snapshot (with a
        warning) and retries only after ERP_RETRY_S, so one ERP blip during a human-gated run never fails a
        step; with no snapshot yet, the failure propagates (nothing to fall back on)."""
        with self._erp_lock:
            now = time.monotonic()
            if self._erp is not None and (now - self._erp_at <= self.erp_ttl_s or now < self._erp_retry_at):
                return self._erp
            try:
                snapshot = ErpSnapshot(self.enterprise.list_materials())
            except Exception as exc:
                if self._erp is None:
                    raise
                log.warning("ERP refresh failed (%s); serving the snapshot from %.0f s ago, next try in %.0f s",
                            type(exc).__name__, now - self._erp_at, ERP_RETRY_S)
                self._erp_retry_at = now + ERP_RETRY_S
                return self._erp
            self._erp, self._erp_at, self._erp_retry_at = snapshot, now, 0.0
            return snapshot

    def inputs(self) -> InputFiles:
        hall = Path(self.scenarios_dir) / "hall_a"
        return InputFiles(tender_pdf=hall / "out" / "tender-hall-a.pdf", plan_pdf=hall / "out" / "hall-a-plan.pdf",
                          dxf=hall / "out" / "hall-a.dxf", ground_truth=hall / "ground_truth.yaml")
