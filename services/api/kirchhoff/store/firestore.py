from google.cloud import firestore


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

    def list_docs(self, collection_path: str) -> list[dict]:
        return [s.to_dict() for s in self._db.collection(collection_path).order_by("__name__").stream()]
