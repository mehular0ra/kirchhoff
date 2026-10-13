import copy
import threading
from typing import Any, Callable

from . import Write


def _deep_merge(dst: dict, src: dict) -> None:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value


class MemoryStore:
    """Thread-safe in-memory Store for tests. Paths look like 'a/b/c/d' (even segment count = document)."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._lock = threading.RLock()

    def set_doc(self, path: str, data: dict) -> None:
        with self._lock:
            self._docs[path] = copy.deepcopy(data)

    def update_doc(self, path: str, data: dict) -> None:
        with self._lock:
            existing = self._docs.setdefault(path, {})
            _deep_merge(existing, copy.deepcopy(data))

    def get_doc(self, path: str) -> dict | None:
        with self._lock:
            d = self._docs.get(path)
            return copy.deepcopy(d) if d is not None else None

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        with self._lock:
            for path, data in items:
                self._docs[path] = copy.deepcopy(data)

    def list_docs(self, collection_path: str, order_by: str | None = None,
                  descending: bool = False, limit: int | None = None) -> list[dict]:
        prefix = collection_path.rstrip("/") + "/"
        depth = collection_path.count("/") + 2
        with self._lock:
            keys = sorted(k for k in self._docs if k.startswith(prefix) and k.count("/") + 1 == depth)
            docs = [copy.deepcopy(self._docs[k]) for k in keys]
        if order_by is None:
            if descending:
                docs = list(reversed(docs))
        else:
            docs.sort(key=lambda d: d.get(order_by), reverse=descending)
        if limit is not None:
            docs = docs[:limit]
        return docs

    def transact(self, read_paths: list[str],
                 fn: Callable[[dict[str, dict | None]], list[Write]]) -> list[Write]:
        with self._lock:
            snapshot: dict[str, dict | None] = {p: self.get_doc(p) for p in read_paths}
            writes = fn(snapshot)
            for path, data in writes:
                if data is None:
                    self._docs.pop(path, None)
                else:
                    self._docs[path] = copy.deepcopy(data)
            return writes

    def delete_tree(self, path: str) -> int:
        with self._lock:
            keys = [k for k in self._docs if k == path or k.startswith(path + "/")]
            for k in keys:
                del self._docs[k]
            return len(keys)
