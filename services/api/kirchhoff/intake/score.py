from pathlib import Path

import yaml
from pydantic import BaseModel

from kirchhoff.contracts import DesignBrief

from .textnorm import normalize


class GTRequirement(BaseModel):
    clause: str
    value: float | int | str | None = None
    unit: str | None = None


class GTContradiction(BaseModel):
    id: str
    clauses: list[str]
    default_resolution: str


class GroundTruth(BaseModel):
    doc_id: str
    clause_pages: dict[str, int]
    requirements: list[GTRequirement]
    contradictions: list[GTContradiction] = []
    drawing: dict = {}


def load_ground_truth(path: Path | str) -> GroundTruth:
    return GroundTruth.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def _canon(s: str) -> str:
    return normalize(s).casefold().replace(" ", "")


def value_matches(gt: float | int | str | None, ex: float | int | str | None) -> bool:
    if gt is None:
        return True
    if ex is None:
        return False
    if isinstance(gt, str):
        return _canon(gt) in _canon(str(ex))
    try:
        return abs(float(str(ex).replace(",", "")) - float(gt)) <= 1e-6 * max(1.0, abs(float(gt)))
    except ValueError:
        return False


def score_intake(brief: DesignBrief, gt: GroundTruth) -> dict[str, float]:
    verified = [r for r in brief.requirements if r.verified]
    used: set[int] = set()
    matched = 0
    for g in gt.requirements:
        for i, r in enumerate(verified):
            if i not in used and r.citation.clause == g.clause and value_matches(g.value, r.value):
                used.add(i)
                matched += 1
                break
    resolved = sum(1 for r in verified if gt.clause_pages.get(r.citation.clause or "") == r.citation.page)
    found_pairs = {(tuple(sorted(c.clause or "" for c in q.citations)), q.default_resolution)
                   for q in brief.open_questions}
    found = sum(1 for c in gt.contradictions if (tuple(sorted(c.clauses)), c.default_resolution) in found_pairs)
    n = len(verified)
    return {"extracted": float(len(brief.requirements)), "verified": float(n),
            "recall": matched / len(gt.requirements) if gt.requirements else 0.0,
            "precision": matched / n if n else 0.0,
            "citation_resolution": resolved / n if n else 0.0,
            "contradictions_found": float(found), "contradictions_expected": float(len(gt.contradictions))}
