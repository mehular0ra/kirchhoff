"""P4 Task 15 (issue #15): infra/appcheck.sh. Order matters because a mistake locks every judge out, so besides the
static checks the script is run under real bash against fake `gcloud` and `curl` binaries that record every call:
which services it would patch, in which mode, and that the debug-token value never reaches a command line or output."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "infra" / "appcheck.sh"
SERVICES = ("firestore.googleapis.com", "firebasestorage.googleapis.com", "firebaseml.googleapis.com")
TOKEN = "11111111-2222-4333-8444-555555555555"  # synthetic: stands in for the secret's value in the fakes
UUID4 = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is needed to run infra scripts")

FAKE_GCLOUD = """#!/usr/bin/env bash
echo "gcloud $*" >> "$FAKE_LOG"
case "$1 $2" in
  "auth print-access-token") echo fake-access-token ;;
  "services enable") ;;
  "secrets describe") [ "${FAKE_SECRET_EXISTS:-1}" = "1" ] ;;
  "secrets create") cat > "$FAKE_DIR/created_secret_value" ;;
  "secrets versions") printf '%s' "$FAKE_SECRET_VALUE" ;;
  *) echo "unexpected gcloud $*" >&2; exit 99 ;;
esac
"""

FAKE_CURL = """#!/usr/bin/env bash
method=GET; url=""; body=""
while [ $# -gt 0 ]; do
  case "$1" in
    -X) method="$2"; shift ;;
    -d) if [ "$2" = "@-" ]; then body="$(cat)"; else body="$2"; fi; shift ;;
    -H) shift ;;
    -*) ;;
    *) url="$1" ;;
  esac
  shift
done
printf '%s %s %s\\n' "$method" "$url" "$body" >> "$FAKE_LOG"
case "$method" in
  GET)
    case "$url" in
      */debugTokens) tokens="${FAKE_DEBUG_TOKENS-}"; [ -n "$tokens" ] || tokens='{}'; printf '%s' "$tokens" ;;
      */services/*) printf '{"enforcementMode": "%s"}' "${FAKE_MODE:-UNENFORCED}" ;;
    esac ;;
  *) printf '{}' ;;
esac
"""


@pytest.fixture
def fakes(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gcloud", FAKE_GCLOUD), ("curl", FAKE_CURL)):
        (bin_dir / name).write_text(body, encoding="utf-8", newline="\n")
    # `python3` on a developer machine may be a Store stub: point it at the interpreter running the tests.
    (bin_dir / "python3").write_text(f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n',
                                     encoding="utf-8", newline="\n")
    log = tmp_path / "calls.log"
    log.write_text("", encoding="utf-8")
    return tmp_path, bin_dir, log


def run(fakes, *args, **env):
    tmp, bin_dir, log = fakes
    full = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": log.as_posix(),
            "FAKE_DIR": tmp.as_posix(), "FAKE_SECRET_VALUE": TOKEN, **env}
    done = subprocess.run(["bash", SCRIPT.as_posix(), *args], capture_output=True, text=True, env=full, timeout=60)
    return done, log.read_text(encoding="utf-8").splitlines()


def patches(calls):
    return [c for c in calls if c.startswith("PATCH ")]


# ---- static: what the committed files say -----------------------------------------------------------------------
def test_appcheck_script_targets_the_three_services_and_keeps_the_token_secret():
    text = SCRIPT.read_text(encoding="utf-8")
    for service in SERVICES:
        assert service in text, service
    assert "firebasevertexai.googleapis.com" not in text  # the API rejects it (ruling W13)
    assert "kirchhoff-e2e-appcheck-debug-token" in text and "1:1015632998221:web:c98110f2fc88424da81104" in text
    assert not re.search(UUID4, text)  # no literal token


def test_api_env_declares_the_app_check_switch_and_it_stays_off_until_the_staged_enforcement():
    """Task 15 flips this to "1" only after the first deploy and a green e2e with the debug token (issue #15 step 2)."""
    env = yaml.safe_load((REPO / "infra" / "api.env.yaml").read_text(encoding="utf-8"))
    assert env["KIRCHHOFF_REQUIRE_APPCHECK"] in ("0", "1")


def test_playwright_injects_the_debug_token_without_touching_the_app():
    fixtures = (REPO / "e2e" / "tests" / "fixtures.ts").read_text(encoding="utf-8")
    assert "addInitScript" in fixtures and "FIREBASE_APPCHECK_DEBUG_TOKEN" in fixtures
    assert "kirchhoff-e2e-appcheck-debug-token" in (REPO / "Makefile").read_text(encoding="utf-8")


# ---- behaviour: the real script under real bash, fake gcloud and curl ------------------------------------------
@needs_bash
def test_no_arguments_prints_usage_and_changes_nothing(fakes):
    done, calls = run(fakes)
    assert done.returncode == 2 and "usage:" in done.stderr and patches(calls) == []


@needs_bash
def test_status_reads_the_three_services_and_writes_nothing(fakes):
    done, calls = run(fakes, "status", FAKE_MODE="UNENFORCED")
    assert done.returncode == 0, done.stderr
    assert [line.split() for line in done.stdout.strip().splitlines()] == [[s, "UNENFORCED"] for s in SERVICES]
    assert all(c.startswith("GET ") for c in calls if not c.startswith("gcloud"))


@needs_bash
def test_enforce_refuses_without_the_explicit_confirmation(fakes):
    """The one command that can lock every judge out must not run by accident (Mehul's "go" comes first)."""
    done, calls = run(fakes, "enforce")
    assert done.returncode != 0 and "APPCHECK_ENFORCE_CONFIRM=yes" in done.stderr
    assert patches(calls) == []


@needs_bash
def test_enforce_with_the_confirmation_patches_exactly_the_three_services(fakes):
    done, calls = run(fakes, "enforce", APPCHECK_ENFORCE_CONFIRM="yes", FAKE_MODE="ENFORCED")
    assert done.returncode == 0, done.stderr
    sent = patches(calls)
    assert len(sent) == 3
    for service, call in zip(SERVICES, sent):
        assert f"/services/{service}?updateMask=enforcementMode" in call and call.endswith('{"enforcementMode": "ENFORCED"}')
    assert done.stdout.strip().splitlines()[-3:] == [f"{s} ENFORCED" for s in SERVICES]  # ends by showing the status


@needs_bash
def test_enforce_can_target_one_service_and_rejects_an_unknown_one(fakes):
    done, calls = run(fakes, "enforce", "firestore.googleapis.com", APPCHECK_ENFORCE_CONFIRM="yes")
    assert done.returncode == 0, done.stderr
    assert len(patches(calls)) == 1 and "/services/firestore.googleapis.com?" in patches(calls)[0]
    done, calls = run(fakes, "enforce", "firebasevertexai.googleapis.com", APPCHECK_ENFORCE_CONFIRM="yes")
    assert done.returncode == 2 and len(patches(calls)) == 1  # still only the first run's single patch


@needs_bash
def test_unenforce_is_the_rollback_and_needs_no_confirmation(fakes):
    done, calls = run(fakes, "unenforce")
    assert done.returncode == 0, done.stderr
    sent = patches(calls)
    assert len(sent) == 3 and all(c.endswith('{"enforcementMode": "UNENFORCED"}') for c in sent)


@needs_bash
def test_debug_token_registers_the_secret_value_over_stdin_and_never_prints_it(fakes):
    done, calls = run(fakes, "debug-token", FAKE_SECRET_EXISTS="1")
    assert done.returncode == 0, done.stderr
    assert TOKEN not in done.stdout and TOKEN not in done.stderr
    assert not any(c.startswith("gcloud secrets create") for c in calls)  # reused, not recreated
    posts = [c for c in calls if c.startswith("POST ")]
    assert len(posts) == 1 and "/apps/1:1015632998221:web:c98110f2fc88424da81104/debugTokens " in posts[0]
    assert '"displayName": "playwright-e2e"' in posts[0] and TOKEN in posts[0]
    assert not any(TOKEN in c for c in calls if c.startswith("gcloud"))  # never on a gcloud command line either


@needs_bash
def test_debug_token_is_idempotent_when_already_registered(fakes):
    registered = '{"debugTokens": [{"displayName": "playwright-e2e"}]}'
    done, calls = run(fakes, "debug-token", FAKE_DEBUG_TOKENS=registered)
    assert done.returncode == 0 and "already registered" in done.stdout
    assert not [c for c in calls if c.startswith("POST ")]


@needs_bash
def test_debug_token_creates_the_secret_with_a_random_uuid_when_it_is_missing(fakes):
    tmp = fakes[0]
    done, calls = run(fakes, "debug-token", FAKE_SECRET_EXISTS="0")
    assert done.returncode == 0, done.stderr
    created = (tmp / "created_secret_value").read_text(encoding="utf-8")
    assert re.fullmatch(UUID4, created) and created not in done.stdout + done.stderr
    assert any(c.startswith("gcloud secrets create kirchhoff-e2e-appcheck-debug-token") for c in calls)
