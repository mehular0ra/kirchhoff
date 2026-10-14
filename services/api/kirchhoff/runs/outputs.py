"""Step outputs (R3): JSON string in Firestore (avoids nested-array limits), or Cloud Storage above 400 KB."""
import hashlib
import json

from kirchhoff.store import Store

from .blobs import BlobStore

INLINE_MAX_BYTES = 400_000


def outputs_path(run_path: str, step_id: str) -> str:
    return f"{run_path}/outputs/{step_id}"


def pack_outputs(blobs: BlobStore, run_path: str, step_id: str, data: dict) -> tuple[str, dict]:
    """I-2: the blob path is content-addressed (the sha256 prefix, not the bare step id). A stale
    worker's late pre-commit write for the same step_id, with different data, then lands on a different
    path and can never overwrite the blob a committing attempt already wrote."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    path = outputs_path(run_path, step_id)
    if len(raw) <= INLINE_MAX_BYTES:
        return path, {"step": step_id, "json": raw.decode("utf-8")}
    digest = hashlib.sha256(raw).hexdigest()
    blob = f"{run_path}/outputs/{step_id}.{digest[:16]}.json"
    blobs.put(blob, raw, "application/json")
    return path, {"step": step_id, "blob": blob, "sha256": digest}


def load_outputs(store: Store, blobs: BlobStore, run_path: str, step_id: str) -> dict | None:
    doc = store.get_doc(outputs_path(run_path, step_id))
    if doc is None:
        return None
    if "json" in doc:
        return json.loads(doc["json"])
    raw = blobs.get(doc["blob"])
    digest = hashlib.sha256(raw).hexdigest()
    if digest != doc["sha256"]:
        raise ValueError(f"blob {doc['blob']} sha256 mismatch for step {step_id}: "
                         f"expected {doc['sha256']}, got {digest}")
    return json.loads(raw.decode("utf-8"))
