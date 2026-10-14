import json
from pathlib import Path

from kirchhoff.enterprise.model import seed_hash
from kirchhoff.enterprise.seed_cli import main, upload_docs


def test_dry_run_prints_the_hash_and_writes_nothing(tmp_path, small_seed, capsys):
    p = tmp_path / "seed.json"
    p.write_text(small_seed.model_dump_json(), encoding="utf-8")
    assert main(["--seed", str(p), "--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hash"] == seed_hash(small_seed) and out["materials"] == 3 and "written" not in out


def test_upload_docs_sets_content_type_and_cache(tmp_path):
    (tmp_path / "hall-a").mkdir()
    (tmp_path / "hall-a" / "calc-report.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "hall-a" / "boq.csv").write_text("x\n", encoding="utf-8")

    class Blob:
        def __init__(self, name):
            self.name, self.cache_control, self.uploaded = name, None, None

        def upload_from_filename(self, path, content_type):
            self.uploaded = (Path(path).name, content_type)

    class Bucket:
        def __init__(self):
            self.blobs = []

        def blob(self, name):
            self.blobs.append(Blob(name))
            return self.blobs[-1]

    bucket = Bucket()
    assert upload_docs(tmp_path, bucket) == ["seed/files/hall-a/boq.csv", "seed/files/hall-a/calc-report.pdf"]
    assert [(b.uploaded[1], b.cache_control) for b in bucket.blobs] == [
        ("text/csv", "public, max-age=300"), ("application/pdf", "public, max-age=300")]


def test_dry_run_reports_the_inbox(tmp_path, small_seed, capsys):
    seed = tmp_path / "seed.json"
    seed.write_text(small_seed.model_dump_json(), encoding="utf-8")
    assert main(["--seed", str(seed), "--inbox", str(tmp_path / "none.json"), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["inbox_emails"] == 0
