import importlib.util
import re
import subprocess
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[4]
INFRA = REPO / "infra"


def _joined(path: Path) -> list[str]:
    """Script lines with backslash continuations joined, comments dropped."""
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def test_shell_scripts_parse():
    for sh in sorted(INFRA.glob("*.sh")):
        r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
        assert r.returncode == 0, f"{sh.name}: {r.stderr}"


def test_every_gcloud_call_names_the_project_and_nobody_sets_config():
    for sh in sorted(INFRA.glob("*.sh")):
        for line in _joined(sh):
            assert "gcloud config set" not in line, sh.name
            for call in re.findall(r"gcloud (?!auth )[^|;&)]*", line):
                if call.startswith("gcloud billing "):  # billing-account scoped: the quota project must be ours
                    assert "--billing-project=" in call, f"{sh.name}: {call}"
                elif not re.match(r"gcloud projects [a-z-]+ (\$P|ordinal-mep)\b", call):  # positional project
                    assert "--project=" in call, f"{sh.name}: {call}"


def test_env_files():
    api = yaml.safe_load((INFRA / "api.env.yaml").read_text(encoding="utf-8"))
    assert api["GOOGLE_CLOUD_PROJECT"] == "ordinal-mep" and api["GOOGLE_GENAI_USE_VERTEXAI"] == "true"
    assert api["GOOGLE_CLOUD_LOCATION"] == "global" and api["GOOGLE_CLOUD_QUOTA_PROJECT"] == "ordinal-mep"
    assert api["KIRCHHOFF_SCENARIOS_DIR"] == "/app/scenarios" and api["KIRCHHOFF_SEED_DIR"] == "/app/seed"
    # #15 ordering: debug token, then a green e2e on the deployed site with it, and only then this flag "1" plus a redeploy;
    # Firestore, Storage and AI Logic are enforced (infra/appcheck.sh) on Mehul's "go" after the golden capture. So it is "0"
    # until then. Both values are valid here, so the flip needs no test edit (this is the one assertion on the switch).
    assert api["KIRCHHOFF_REQUIRE_APPCHECK"] in ("0", "1")
    assert "KIRCHHOFF_ENTERPRISE_URL" not in api  # injected by deploy_api.sh from the live service URL
    assert all(isinstance(v, str) for v in api.values())
    assert not {"KIRCHHOFF_FAKES", "KIRCHHOFF_BLOBS", "KIRCHHOFF_RECORD_DIR"} & set(api)  # local development only
    ent = yaml.safe_load((INFRA / "enterprise.env.yaml").read_text(encoding="utf-8"))
    assert ent["GOOGLE_CLOUD_PROJECT"] == "ordinal-mep" and all(isinstance(v, str) for v in ent.values())


def test_deploy_script_is_guarded_and_uses_the_runtime_account():
    text = " ".join(_joined(INFRA / "deploy_api.sh"))
    assert "uv lock --check" in text and not re.search(r"uv lock(?! --check)", text)
    assert "live_runs.py" in text and "build_context.sh" in text and "gcloud builds submit" in text
    assert text.count("--service-account=") == 2 and "kirchhoff-runtime@" in text
    assert "--no-allow-unauthenticated" in text and "kirchhoff.enterprise.app:create_enterprise_app" in text
    assert "--min-instances=1 --max-instances=2" in text and "--min-instances=1 --max-instances=3" in text


def test_iam_setup_grants_only_the_listed_roles():
    text = " ".join(_joined(INFRA / "iam_setup.sh"))
    roles = sorted(set(re.findall(r"roles/[A-Za-z.]+", text)))
    assert roles == ["roles/aiplatform.user", "roles/datastore.user", "roles/iam.serviceAccountTokenCreator",
                     "roles/logging.logWriter", "roles/storage.objectAdmin"]
    assert "iamcredentials.googleapis.com" in text


def _live_runs():
    spec = importlib.util.spec_from_file_location("live_runs", INFRA / "live_runs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_run_guard_counts_only_fresh_leases():
    lr = _live_runs()
    assert lr.live_count(None, 1000.0) == 0
    assert lr.live_count({"runs": {"u__a": 990.0, "u__b": 900.0, "u__c": "bad"}}, 1000.0) == 1


def test_smoke_probes_whoami_and_the_private_sandbox():
    text = " ".join(_joined(INFRA / "smoke.sh"))
    assert "/api/whoami" in text and "hello-run" not in text
    assert "/api/enterprise/erp/materials" in text and '"403"' in text
    assert text.index("/api/whoami") < text.index("http://localhost*") < text.index('<div id="root">')  # API-only locally
