"""Bids inbox data for the API: the seed (Firestore seed/inbox, else the image's inbox_seed.json) and the visitor's
overlay (workspaces/{uid}/inbox/{email_id}), merged into the InboxSnapshot the web app renders."""
from pathlib import Path

from kirchhoff.enterprise.world.inbox import SEED_DOC, SEED_EMAILS, InboxSeed, load_inbox_seed
from kirchhoff.store import Store


def overlay_path(uid: str, email_id: str) -> str:
    return f"workspaces/{uid}/inbox/{email_id}"


def project_path(uid: str, project_id: str) -> str:
    return f"workspaces/{uid}/projects/{project_id}"


def load_seed(store: Store, scenarios_dir: Path) -> InboxSeed:
    meta = store.get_doc(SEED_DOC)
    if meta is not None:
        return InboxSeed.model_validate({**meta, "emails": store.list_docs(SEED_EMAILS)})
    return load_inbox_seed(Path(scenarios_dir) / "demo_world" / "out" / "inbox_seed.json")


def overlays(store: Store, uid: str) -> dict[str, dict]:
    return {d["email_id"]: d for d in store.list_docs(f"workspaces/{uid}/inbox") if d.get("email_id")}


def inbox_view(seed: InboxSeed, overlay: dict[str, dict]) -> dict:
    emails = []
    for e in sorted(seed.emails, key=lambda m: (-m.received_at, m.id)):
        ov = overlay.get(e.id, {})
        emails.append({**e.model_dump(mode="json"), "triage": ov.get("triage") or (e.triage or None),
                       "status": ov.get("status", "new"), "pursue": ov.get("pursue")})
    return {**seed.model_dump(mode="json", exclude={"emails"}), "emails": emails}
