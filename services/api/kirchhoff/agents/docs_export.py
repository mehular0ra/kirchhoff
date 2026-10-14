"""Docs exports. Wed: Exporter protocol + StubExporter. Thu (Task 18): BlobExporter (reportlab PDF + BOQ CSV)."""
from typing import Protocol

from kirchhoff.contracts import DesignBrief, Finding, PRLine, Revision, TopologyOption

SECTIONS = ["summary", "requirements", "options", "findings", "fixes", "ledger", "boq"]


class Exporter(Protocol):
    def export(self, *, uid: str, rev: Revision, findings: list[Finding], fixes: list[Finding],
               brief: DesignBrief | None, options: list[TopologyOption], pr_lines: list[PRLine], order: list[str],
               summary: str) -> list[dict]: ...


class StubExporter:
    def export(self, **_: object) -> list[dict]:
        return [{"name": "calc-report.pdf", "path": None, "status": "pending"},
                {"name": "boq.csv", "path": None, "status": "pending"}]
