"""Step outputs (R3): JSON string in Firestore (avoids nested-array limits), or Cloud Storage above 400 KB."""
import hashlib
import json

from kirchhoff.store import Store

from .blobs import BlobStore

INLINE_MAX_BYTES = 400_000


def outputs_path(run_path: str, step_id: str) -> str:
    return f"{run_path}/outputs/{step_id}"


def pack_outputs(blobs: BlobStore, run_path: str, step_id: str, data: dict) -> tuple[str, dict]:
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    path = outputs_path(run_path, step_id)
    if len(raw) <= INLINE_MAX_BYTES:
        return path, {"step": step_id, "json": raw.decode("utf-8")}
    blob = f"{run_path}/outputs/{step_id}.json"
    blobs.put(blob, raw, "application/json")
    return path, {"step": step_id, "blob": blob, "sha256": hashlib.sha256(raw).hexdigest()}


def load_outputs(store: Store, blobs: BlobStore, run_path: str, step_id: str) -> dict | None:
    doc = store.get_doc(outputs_path(run_path, step_id))
    if doc is None:
        return None
    raw = doc["json"] if "json" in doc else blobs.get(doc["blob"]).decode("utf-8")
    return json.loads(raw)
