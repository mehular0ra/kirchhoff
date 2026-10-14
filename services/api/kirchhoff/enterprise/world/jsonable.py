"""Turn engine result dicts (pydantic models, tuples, numpy scalars) into plain JSON values for static bundles."""
import math
from typing import Any

from pydantic import BaseModel


def jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):  # numpy scalar
        return jsonable(value.item())
    return str(value)
