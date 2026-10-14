import io
import json

import pdfplumber
import pytest

from kirchhoff.enterprise.model import FICTIONAL_NOTICE, ILLUSTRATIVE
from kirchhoff.enterprise.world.inbox import (INBOX_DIR, INBOX_JSON, INBOX_OUT_DIR, INBOX_SEED, SEED_DOC, SEED_EMAILS,
                                              InboxSeed, build_inbox, inbox_diff_on_disk, load_inbox,
                                              load_triage_capture, write_inbox)
from kirchhoff.store.memory import MemoryStore

DAY = 86400.0


@pytest.fixture(scope="module")
def build(world_cfg, scenarios_root):
    return build_inbox(world_cfg, scenarios_root)


def _text(pdf: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return " ".join(" ".join((p.extract_text() or "").split()) for p in doc.pages)


def test_the_six_spec_20_emails_newest_first(build, world_cfg):
    seed = build.seed
    assert seed.mailbox == "bids@meridian-power.example" and seed.label == "sandbox (simulated)"
    assert seed.notice == FICTIONAL_NOTICE and seed.as_of == world_cfg.now
    assert [e.id for e in seed.emails] == ["em-hall-b", "em-tapti-brochure", "em-konkan-rfi", "em-vindhya-boq",
                                           "em-suryodaya-solar", "em-narmada-400kv"]
    assert all(world_cfg.now - 10 * DAY <= e.received_at <= world_cfg.now for e in seed.emails)
    assert [e.id for e in seed.emails if e.live_triage] == ["em-hall-b"]
    hall_b = seed.emails[0]
    assert hall_b.project_id == "hall-b" and hall_b.to == seed.mailbox
    assert [(a.id, a.url, a.source) for a in hall_b.attachments] == [
        ("att-hall-b-tender", "/demo/docs/tender-hall-a.pdf", "hall_a/out/tender-hall-a.pdf"),
        ("att-hall-b-drawing", "/demo/docs/hall-a-plan.pdf", "hall_a/out/hall-a-plan.pdf"),
        ("att-hall-b-addendum", "/demo/inbox/hall-b-addendum-1.pdf", "demo_world/out/inbox/hall-b-addendum-1.pdf")]
    assert {e.id: len(e.attachments) for e in seed.emails}["em-suryodaya-solar"] == 0
    assert all(e.triage is None for e in seed.emails)


def test_appetite_rules(build):
    a = build.seed.appetite
    assert a.asset_types == ["datahall", "grid", "solar"] and a.mw == (2.0, 120.0)
    assert a.min_days_to_bid_due == 10 and a.lead_time_check is True
    assert [r.name for r in a.regions] == ["Telangana", "Andhra Pradesh", "Karnataka", "Maharashtra", "Madhya Pradesh"]


def test_attachments_are_deterministic_and_labelled(build, world_cfg, scenarios_root):
    assert build_inbox(world_cfg, scenarios_root).digest() == build.digest()
    addendum = _text(build.files[f"{INBOX_DIR}/hall-b-addendum-1.pdf"])
    for quote in ("Hall B IT load: 6.336 MW", "Bids are due by 13 November 2026",
                  "no later than 26 weeks from contract award", ILLUSTRATIVE, "Demo workspace - all companies"):
        assert quote in addendum, quote
    with pdfplumber.open(io.BytesIO(build.files[f"{INBOX_DIR}/vindhya-boq-scan.pdf"])) as scan:
        assert len(scan.pages) == 1 and not scan.pages[0].extract_text() and len(scan.pages[0].images) == 1


def test_static_and_api_copies_are_identical(build, scenarios_root):
    assert build.files[INBOX_JSON] == build.files[INBOX_SEED]
    assert InboxSeed.model_validate_json(build.files[INBOX_JSON]) == build.seed
    web = {k.rsplit("/", 1)[1]: v for k, v in build.files.items() if k.startswith(INBOX_DIR + "/")}
    api = {k.rsplit("/", 1)[1]: v for k, v in build.files.items() if k.startswith(INBOX_OUT_DIR + "/")}
    assert web == api and sorted(web) == ["hall-b-addendum-1.pdf", "konkan-rfi-response.pdf",
                                          "narmada-400kv-spec.pdf", "tapti-brochure.pdf", "vindhya-boq-scan.pdf"]
    assert all((scenarios_root / a.source).is_file() for e in build.seed.emails for a in e.attachments
               if a.source.startswith("hall_a/"))


def test_triage_capture_is_folded_in_and_checked(world_cfg, scenarios_root, tmp_path):
    result = {"email_id": "em-hall-b", "fit": {"verdict": "pursue"}}
    seed = build_inbox(world_cfg, scenarios_root, {"em-hall-b": result}).seed
    assert next(e for e in seed.emails if e.id == "em-hall-b").triage == result
    with pytest.raises(ValueError, match="unknown emails"):
        build_inbox(world_cfg, scenarios_root, {"em-nope": {"email_id": "em-nope"}})
    with pytest.raises(ValueError, match="carries email_id"):
        build_inbox(world_cfg, scenarios_root, {"em-hall-b": {"email_id": "em-konkan-rfi"}})
    assert load_triage_capture(tmp_path / "missing.json") == {}
    capture = tmp_path / "inbox-triage.json"
    capture.write_text(json.dumps({"version": 1, "results": {"em-hall-b": result}}), encoding="utf-8")
    assert load_triage_capture(capture) == {"em-hall-b": result}
    capture.write_text(json.dumps({"version": 2, "results": {}}), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        load_triage_capture(capture)


def test_write_prunes_stale_files_and_check_detects_drift(build, tmp_path):
    stale = tmp_path / INBOX_DIR / "old.pdf"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"%PDF")
    write_inbox(build, tmp_path)
    assert not stale.exists() and inbox_diff_on_disk(build, tmp_path) == []
    (tmp_path / INBOX_JSON).write_text("{}", encoding="utf-8")
    (tmp_path / INBOX_OUT_DIR / "extra.pdf").write_bytes(b"%PDF")
    assert inbox_diff_on_disk(build, tmp_path) == [INBOX_JSON, f"{INBOX_OUT_DIR}/extra.pdf"]


def test_seed_loader_writes_seed_inbox(build):
    store = MemoryStore()
    store.set_doc(f"{SEED_EMAILS}/em-stale", {"id": "em-stale"})
    assert load_inbox(store, build.seed) == 6
    meta = store.get_doc(SEED_DOC)
    assert "emails" not in meta and meta["as_of"] == build.seed.as_of and meta["appetite"]["mw"] == [2.0, 120.0]
    assert sorted(d["id"] for d in store.list_docs(SEED_EMAILS)) == sorted(e.id for e in build.seed.emails)
