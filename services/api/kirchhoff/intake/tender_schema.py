"""Reader for WS1's scenarios/hall_a/tender.yaml (P1 engine plan, Task 1)."""
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .textnorm import normalize

CLAUSE_ID_RE = re.compile(r"^(§\d+(?:\.\d+)*|App\. [A-Z])$")
LimitValue = float | int | str | list[str]


class TenderClause(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    page: int
    text: str
    quote: str
    limits: dict[str, LimitValue] = {}

    @property
    def section(self) -> str:
        return "appendix" if self.id.startswith("App. ") else "main"

    @field_validator("id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not CLAUSE_ID_RE.match(v):
            raise ValueError(f"clause id {v!r} must look like '§4.6' or 'App. B'")
        return v

    @field_validator("title", "text", "quote")
    @classmethod
    def _latin1(cls, v: str) -> str:
        try:
            v.encode("latin-1")
        except UnicodeEncodeError as exc:
            raise ValueError(f"text must be Latin-1 (Helvetica): {exc.object[exc.start:exc.end]!r}") from exc
        return v

    @model_validator(mode="after")
    def _quote_in_text(self) -> "TenderClause":
        if normalize(self.quote) not in normalize(self.text):
            raise ValueError(f"clause {self.id}: quote is not a verbatim substring of text")
        return self


class TenderDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")
    doc_id: str
    title: str
    client: str
    site: str = ""
    reference: str
    notice: str = ""
    clauses: list[TenderClause]

    @model_validator(mode="after")
    def _ordering(self) -> "TenderDoc":
        ids = [c.id for c in self.clauses]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate clause ids")
        pages = [c.page for c in self.clauses]
        if pages != sorted(pages) or pages[0] != 1:
            raise ValueError("clauses must be in page order starting on page 1")
        return self

    def clause(self, cid: str) -> TenderClause:
        return next(c for c in self.clauses if c.id == cid)

    def limit(self, key: str) -> LimitValue:
        return next(c.limits[key] for c in self.clauses if key in c.limits)


def load_tender(path: Path | str) -> TenderDoc:
    return TenderDoc.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
