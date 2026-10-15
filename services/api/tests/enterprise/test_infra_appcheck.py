"""P4 Task 15 (issue #15): infra/appcheck.sh. Order matters because a mistake locks every judge out, so besides the
static checks the script is run under real bash against stub `gcloud` and `curl` binaries that record every call:
which services it would patch, in which mode, and that the debug-token value never reaches a command line or output.

SAFETY (incident of 15 Oct 14:49 IST: non-executable stubs let bash fall through to the REAL gcloud and curl, and a
test run enforced App Check on ordinal-mep). Four independent layers now stop that from happening again:
  1. every stub is chmod 755;
  2. the fixture proves, through bash itself, that the stubs are what `command -v` finds first, so EVERY test errors at
     setup if a stub does not resolve first;
  3. a DECOY "real" gcloud and curl sit behind the stubs on PATH; if any is ever run, the test fails at teardown;
  4. the script takes its tools from APPCHECK_FAKE_DIR only (never PATH) when that is set, stops if a stub is missing or
     not executable, and refuses to run under pytest at all without it (tests below);
  5. the environment of every run has no credentials: CLOUDSDK_CONFIG is an empty directory, GOOGLE_APPLICATION_CREDENTIALS
     and CLOUDSDK_AUTH_* are not passed on, and APPCHECK_FAKE_DIR / APPCHECK_ENFORCE_CONFIRM exported in the caller's
     shell are dropped. This is the one layer that depends on neither PATH nor the script."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[4]
SCRIPT = REPO / "infra" / "appcheck.sh"
SERVICES = ("firestore.googleapis.com", "firebasestorage.googleapis.com", "firebaseml.googleapis.com")
TOKEN = "11111111-2222-4333-8444-555555555555"  # synthetic: stands in for the secret's value in the stubs
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

# Stands in for the REAL tools: if a test ever runs it, the project could have been reached.
DECOY = """#!/usr/bin/env bash
echo "THE REAL $(basename "$0") WAS CALLED: $*" >> "$DECOY_LOG"
exit 99
"""


def _executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(0o755)  # without this, bash skips the file and runs the real binary found later on PATH


@pytest.fixture
def fakes(tmp_path):
    stubs, decoys = tmp_path / "stubs", tmp_path / "decoys"
    stubs.mkdir()
    decoys.mkdir()
    _executable(stubs / "gcloud", FAKE_GCLOUD)
    _executable(stubs / "curl", FAKE_CURL)
    # `python3` on a developer machine may be a Store stub: point it at the interpreter running the tests.
    _executable(stubs / "python3", f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n')
    for name in ("gcloud", "curl"):
        _executable(decoys / name, DECOY)
    log, decoy_log = tmp_path / "calls.log", tmp_path / "decoy.log"
    log.write_text("", encoding="utf-8")
    config = tmp_path / "gcloud-config"  # an EMPTY gcloud configuration directory: no accounts, no credentials
    config.mkdir()
    state = SimpleNamespace(tmp=tmp_path, stubs=stubs, decoys=decoys, log=log, decoy_log=decoy_log, config=config)
    _assert_stubs_resolve_first(state)  # layer 2, for every test: a stub that does not resolve first errors at setup
    yield state
    # Teardown: whatever the test did, the decoy "real" tools were never reached.
    assert not decoy_log.exists(), decoy_log.read_text(encoding="utf-8")


def _env(state, fake_dir=True, **extra):
    # Nothing that could authenticate, or arm the script, is inherited from whoever runs the tests. PYTEST_CURRENT_TEST
    # IS inherited on purpose: the script's pytest guard needs it.
    inherited = {k: v for k, v in os.environ.items()
                 if k not in ("GOOGLE_APPLICATION_CREDENTIALS", "APPCHECK_FAKE_DIR", "APPCHECK_ENFORCE_CONFIRM")
                 and not k.startswith("CLOUDSDK_AUTH_")}
    base = {**inherited, "PATH": os.pathsep.join([str(state.stubs), str(state.decoys), os.environ["PATH"]]),
            "CLOUDSDK_CONFIG": str(state.config),
            "FAKE_LOG": state.log.as_posix(), "FAKE_DIR": state.tmp.as_posix(), "FAKE_SECRET_VALUE": TOKEN,
            "DECOY_LOG": state.decoy_log.as_posix()}
    if fake_dir:
        base["APPCHECK_FAKE_DIR"] = state.stubs.as_posix()
    return {**base, **extra}


def _assert_stubs_resolve_first(state):
    """Layer 2: ask bash itself (not Python's which, which differs on Windows) what each tool name resolves to."""
    done = subprocess.run(["bash", "-c", "command -v gcloud curl python3"], capture_output=True, text=True,
                          env=_env(state, fake_dir=False), timeout=60)
    found = done.stdout.strip().splitlines()
    assert len(found) == 3 and all(state.tmp.name in line and "stubs" in line for line in found), (
        f"gcloud, curl and python3 must all resolve to the stubs first, bash found: {found}")


def run(state, *args, fake_dir=True, **env):
    done = subprocess.run(["bash", SCRIPT.as_posix(), *args], capture_output=True, text=True,
                          env=_env(state, fake_dir, **env), timeout=60)
    return done, state.log.read_text(encoding="utf-8").splitlines()


def patches(calls):
    return [c for c in calls if c.startswith("PATCH ")]


def gets(calls):
    return [c for c in calls if c.startswith("GET ")]


# ---- static: what the committed files say -----------------------------------------------------------------------
def test_appcheck_script_targets_the_three_services_and_keeps_the_token_secret():
    text = SCRIPT.read_text(encoding="utf-8")
    for service in SERVICES:
        assert service in text, service
    assert "firebasevertexai.googleapis.com" not in text  # the API rejects it (ruling W13)
    assert "kirchhoff-e2e-appcheck-debug-token" in text and "1:1015632998221:web:c98110f2fc88424da81104" in text
    assert not re.search(UUID4, text)  # no literal token


def test_playwright_injects_the_debug_token_without_touching_the_app():
    fixtures = (REPO / "e2e" / "tests" / "fixtures.ts").read_text(encoding="utf-8")
    assert "addInitScript" in fixtures and "FIREBASE_APPCHECK_DEBUG_TOKEN" in fixtures
    assert "kirchhoff-e2e-appcheck-debug-token" in (REPO / "Makefile").read_text(encoding="utf-8")


# ---- the safety layers themselves ---------------------------------------------------------------------------------
@needs_bash
def test_under_pytest_the_script_refuses_to_run_without_the_stubs_marker(fakes):
    """Layer 4a: a test that forgets the stubs gets a refusal, never a call to the real project."""
    for args in (["status"], ["enforce"], ["unenforce"], ["debug-token"]):
        # No confirmation here on purpose: the guard fires before argument parsing, so it adds no coverage, and without it a
        # failure of every other layer still cannot confirm an enforce.
        done, calls = run(fakes, *args, fake_dir=False)
        assert done.returncode == 3 and "refusing to run under pytest" in done.stderr, (args, done.stderr)
        assert calls == []


@needs_bash
def test_a_missing_stub_stops_the_script_before_any_call(fakes):
    """Layer 4b: with the marker set, a missing stub is an error, not a fall-through to a real binary on PATH."""
    (fakes.stubs / "gcloud").unlink()
    done, calls = run(fakes, "status")
    assert done.returncode == 4 and "stub gcloud is missing or not executable" in done.stderr
    assert calls == []


@needs_bash
@pytest.mark.skipif(os.name == "nt", reason="Windows has no executable bit to remove")
def test_a_non_executable_stub_stops_the_script_before_any_call(fakes):
    """The incident itself: a stub without the executable bit. Before, bash ran the real binary behind it on PATH."""
    (fakes.stubs / "curl").chmod(0o644)
    done, calls = run(fakes, "enforce", APPCHECK_ENFORCE_CONFIRM="yes")
    assert done.returncode == 4 and "stub curl is missing or not executable" in done.stderr
    assert calls == [] and not fakes.decoy_log.exists()


@needs_bash
def test_the_test_environment_has_no_credentials_and_inherits_no_switches(fakes, monkeypatch):
    """Layer 5 (#22 review): even a real gcloud reached by accident finds no credentials, because CLOUDSDK_CONFIG points
    at an empty directory and no credential variable is passed on; and a switch exported in the caller's shell cannot
    leak into a test."""
    for name, value in {"GOOGLE_APPLICATION_CREDENTIALS": "/real/adc.json", "CLOUDSDK_AUTH_ACCESS_TOKEN": "real-token",
                        "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE": "/real/key.json", "APPCHECK_FAKE_DIR": "/elsewhere",
                        "APPCHECK_ENFORCE_CONFIRM": "yes"}.items():
        monkeypatch.setenv(name, value)
    env = _env(fakes, fake_dir=False)
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in env and not [k for k in env if k.startswith("CLOUDSDK_AUTH_")]
    assert "APPCHECK_FAKE_DIR" not in env and "APPCHECK_ENFORCE_CONFIRM" not in env
    config = Path(env["CLOUDSDK_CONFIG"])
    assert config.is_dir() and not any(config.iterdir()) and fakes.tmp in config.parents
    assert "PYTEST_CURRENT_TEST" in env  # the script's pytest guard only works if the child inherits it


@needs_bash
def test_a_switch_exported_in_the_callers_shell_does_not_count(fakes, monkeypatch):
    """A developer who exported APPCHECK_FAKE_DIR or APPCHECK_ENFORCE_CONFIRM in their own shell must not change what a
    test does: without the fake dir passed on purpose, the script still refuses."""
    monkeypatch.setenv("APPCHECK_FAKE_DIR", fakes.stubs.as_posix())
    monkeypatch.setenv("APPCHECK_ENFORCE_CONFIRM", "yes")
    done, calls = run(fakes, "enforce", fake_dir=False)
    assert done.returncode == 3 and "refusing to run under pytest" in done.stderr
    assert calls == []


@needs_bash
def test_the_fixture_check_fails_when_a_stub_is_not_what_bash_finds_first(fakes):
    """Layer 2 is enforced for every test at fixture setup; prove the check itself bites: take a stub away and bash
    falls through to the decoy, which the check must report."""
    (fakes.stubs / "curl").unlink()
    with pytest.raises(AssertionError, match="curl"):
        _assert_stubs_resolve_first(fakes)


# ---- behaviour: the real script under real bash, stub gcloud and curl ------------------------------------------
@needs_bash
def test_no_arguments_prints_usage_and_changes_nothing(fakes):
    done, calls = run(fakes)
    assert done.returncode == 2 and "usage:" in done.stderr and calls == []


@needs_bash
def test_status_reads_the_three_services_and_writes_nothing(fakes):
    done, calls = run(fakes, "status", FAKE_MODE="UNENFORCED")
    assert done.returncode == 0, done.stderr
    assert [line.split() for line in done.stdout.strip().splitlines()] == [[s, "UNENFORCED"] for s in SERVICES]
    assert len(gets(calls)) == 3 and patches(calls) == []
    assert calls.count("gcloud auth print-access-token") == 3  # the stub gcloud really answered


@needs_bash
def test_enforce_refuses_without_the_explicit_confirmation(fakes):
    """The one command that can lock every judge out must not run by accident (Mehul's "go" comes first)."""
    done, calls = run(fakes, "enforce")
    assert done.returncode == 1 and "APPCHECK_ENFORCE_CONFIRM=yes" in done.stderr
    assert calls == []  # it refused before a single call: no token fetch, no GET, no PATCH


@needs_bash
def test_enforce_with_the_confirmation_patches_exactly_the_three_services(fakes):
    done, calls = run(fakes, "enforce", APPCHECK_ENFORCE_CONFIRM="yes", FAKE_MODE="ENFORCED")
    assert done.returncode == 0, done.stderr
    sent = patches(calls)
    assert len(sent) == 3 and len(gets(calls)) == 3  # three PATCHes, then the status read-back
    for service, call in zip(SERVICES, sent):
        assert f"/services/{service}?updateMask=enforcementMode" in call and call.endswith('{"enforcementMode": "ENFORCED"}')
    assert done.stdout.strip().splitlines()[-3:] == [f"{s} ENFORCED" for s in SERVICES]  # ends by showing the status


@needs_bash
def test_enforce_can_target_one_service_and_rejects_an_unknown_one(fakes):
    done, calls = run(fakes, "enforce", "firestore.googleapis.com", APPCHECK_ENFORCE_CONFIRM="yes")
    assert done.returncode == 0, done.stderr
    assert len(patches(calls)) == 1 and "/services/firestore.googleapis.com?" in patches(calls)[0]
    done, calls = run(fakes, "enforce", "firebasevertexai.googleapis.com", APPCHECK_ENFORCE_CONFIRM="yes")
    assert done.returncode == 2 and "unknown service" in done.stderr
    assert len(patches(calls)) == 1  # still only the first run's single patch: the second sent nothing


@needs_bash
def test_unenforce_is_the_rollback_and_needs_no_confirmation(fakes):
    done, calls = run(fakes, "unenforce")
    assert done.returncode == 0, done.stderr
    sent = patches(calls)
    assert len(sent) == 3 and all(c.endswith('{"enforcementMode": "UNENFORCED"}') for c in sent)
    assert len(gets(calls)) == 3


@needs_bash
def test_debug_token_registers_the_secret_value_over_stdin_and_never_prints_it(fakes):
    done, calls = run(fakes, "debug-token", FAKE_SECRET_EXISTS="1")
    assert done.returncode == 0, done.stderr
    assert TOKEN not in done.stdout and TOKEN not in done.stderr
    assert any(c.startswith("gcloud services enable") for c in calls)  # the stub gcloud really ran
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
    assert len(gets(calls)) == 1 and not [c for c in calls if c.startswith("POST ")]


@needs_bash
def test_debug_token_creates_the_secret_with_a_random_uuid_when_it_is_missing(fakes):
    done, calls = run(fakes, "debug-token", FAKE_SECRET_EXISTS="0")
    assert done.returncode == 0, done.stderr
    created = (fakes.tmp / "created_secret_value").read_text(encoding="utf-8")
    assert re.fullmatch(UUID4, created) and created not in done.stdout + done.stderr
    assert any(c.startswith("gcloud secrets create kirchhoff-e2e-appcheck-debug-token") for c in calls)
