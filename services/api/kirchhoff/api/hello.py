import logging
import os
import threading
import time
import uuid

from fastapi import APIRouter, Depends

from kirchhoff.contracts import RunRecord
from kirchhoff.store import Store
from kirchhoff.store.events import EventWriter

logger = logging.getLogger("kirchhoff")

STEPS = ["Intake reading tender", "Layout placing racks", "Power sizing chain", "Cooling sizing CDUs",
         "Checker verifying"]


def make_router(store: Store, current_uid) -> APIRouter:
    router = APIRouter()

    def _run(uid: str, run_id: str) -> None:
        run_path = f"workspaces/{uid}/runs/{run_id}"
        try:
            interval = float(os.environ.get("KIRCHHOFF_HELLO_INTERVAL_S", "1.0"))
            writer = EventWriter(store, run_path, phase="p1", step="p1.hello", flush_interval_s=0)
            for i, title in enumerate(STEPS):
                writer.emit("system", "status", title, detail=f"step {i + 1} of {len(STEPS)}")
                time.sleep(interval)
            writer.close()
            store.update_doc(run_path, {"status": "done", "finished_at": time.time()})
        except Exception as exc:
            logger.exception(f"hello-run failed for {run_id}")
            try:
                store.update_doc(run_path, {
                    "status": "failed",
                    "finished_at": time.time(),
                    "error": f"{type(exc).__name__}: {str(exc)}"
                })
            except Exception:
                logger.exception(f"failed to update run {run_id} status after error")

    @router.post("/api/hello-run", status_code=202)
    def hello_run(uid: str = Depends(current_uid)) -> dict:
        run_id = uuid.uuid4().hex[:12]
        run = RunRecord(id=run_id, project_id="hello", status="running", autonomy="auto", phase="p1",
                        started_at=time.time())
        store.set_doc(f"workspaces/{uid}/runs/{run_id}", run.model_dump())
        threading.Thread(target=_run, args=(uid, run_id), daemon=True).start()
        return {"run_id": run_id}

    return router
