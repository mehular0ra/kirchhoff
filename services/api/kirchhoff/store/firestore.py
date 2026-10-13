from typing import Callable

from google.cloud import firestore

from . import Write


class FirestoreStore:
    def __init__(self, client: firestore.Client | None = None) -> None:
        self._db = client or firestore.Client(project="ordinal-mep")

    def set_doc(self, path: str, data: dict) -> None:
        self._db.document(path).set(data)

    def update_doc(self, path: str, data: dict) -> None:
        self._db.document(path).set(data, merge=True)

    def get_doc(self, path: str) -> dict | None:
        snap = self._db.document(path).get()
        return snap.to_dict() if snap.exists else None

    def batch_set(self, items: list[tuple[str, dict]]) -> None:
        for i in range(0, len(items), 450):  # Firestore batch limit is 500 writes
            batch = self._db.batch()
            for path, data in items[i:i + 450]:
                batch.set(self._db.document(path), data)
            batch.commit()

    def list_docs(self, collection_path: str, order_by: str | None = None,
                  descending: bool = False, limit: int | None = None) -> list[dict]:
        query = self._db.collection(collection_path).order_by(order_by or "__name__",
            direction=firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING)
        if limit is not None:
            query = query.limit(limit)
        return [s.to_dict() for s in query.stream()]

    def transact(self, read_paths: list[str],
                 fn: Callable[[dict[str, dict | None]], list[Write]]) -> list[Write]:
        transaction = self._db.transaction()

        @firestore.transactional
        def _run(transaction):
            snapshot: dict[str, dict | None] = {}
            for path in read_paths:
                snap = transaction.get(self._db.document(path))
                # transaction.get returns a generator-like / snapshot depending on client version
                if hasattr(snap, "__iter__") and not hasattr(snap, "exists"):
                    snap = next(iter(snap))
                snapshot[path] = snap.to_dict() if snap.exists else None
            writes = fn(snapshot)
            for path, data in writes:
                ref = self._db.document(path)
                if data is None:
                    transaction.delete(ref)
                else:
                    transaction.set(ref, data)
            return writes

        return _run(transaction)

    def delete_tree(self, path: str) -> int:
        segments = path.count("/") + 1
        if segments % 2 == 1:  # odd segment count -> collection
            ref = self._db.collection(path)
        else:
            ref = self._db.document(path)
        return self._db.recursive_delete(ref)
