import json
import math
from typing import Any


def firestore_safe_problems(value: Any, path: str = "$") -> list[str]:
    """Return human-readable problem descriptions for values that Firestore cannot store.

    Checks for: arrays nested directly inside arrays, non-JSON types (e.g. numpy
    scalars, tuples), NaN/Infinity floats, and dict keys that are not non-empty strings.
    """
    problems: list[str] = []

    if isinstance(value, bool):
        return problems
    if value is None or isinstance(value, (int, str)):
        return problems
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            problems.append(f"{path}: NaN/Infinity float is not Firestore-safe")
        return problems
    if isinstance(value, tuple):
        problems.append(f"{path}: tuple is not JSON (expected a list)")
        for i, item in enumerate(value):
            problems.extend(firestore_safe_problems(item, f"{path}[{i}]"))
        return problems
    if isinstance(value, list):
        for i, item in enumerate(value):
            item_path = f"{path}[{i}]"
            if isinstance(item, (list, tuple)):
                problems.append(f"{item_path}: array nested directly inside array")
            problems.extend(firestore_safe_problems(item, item_path))
        return problems
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key == "":
                problems.append(f"{path}: dict key {key!r} is not a non-empty string")
                continue
            problems.extend(firestore_safe_problems(item, f"{path}.{key}"))
        return problems

    problems.append(f"{path}: value of type {type(value).__name__} is not a JSON-safe type")
    return problems


def json_size_bytes(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())
