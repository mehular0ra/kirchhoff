import copy
import threading


class MemoryStore:
    """Thread-safe in-memory Store for tests. Paths look like 'a/b/c/d' (even segment count = document)."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def set_doc(self, path: str, data: dict) -> None:
        with self._lock:
            self._docs[path] = copy.deepcopy(data)

    def update_doc(self, path: str, data: dict) -> None:
        with self._lock:
            self._docs.setdefault(path, {}).update(copy.deepcopy(data))

    def get_doc(self, path: str) -> dict | None:
        with self._lock:
            d = self._docs.get(path)
            return copy.deepcopy(d) if d is not None else None

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        with self._lock:
            for path, data in items:
                self._docs[path] = copy.deepcopy(data)

    def list_docs(self, collection_path: str) -> list[dict]:
        prefix = collection_path.rstrip("/") + "/"
        depth = collection_path.count("/") + 2
        with self._lock:
            keys = sorted(k for k in self._docs if k.startswith(prefix) and k.count("/") + 1 == depth)
            return [copy.deepcopy(self._docs[k]) for k in keys]
