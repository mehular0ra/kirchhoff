import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

# Deviation from the brief (controller ruling P4-R6): the brief's scripts take a single ALERT_EMAIL.
# The repo is public, so no email address may ever be committed, and the controller wants two
# recipients. The scripts now read a comma-separated ALERT_EMAILS and still accept a single
# ALERT_EMAIL for one address, creating/reusing one channel per address (matched by its
# email_address label, never by display name) and attaching all of them to both policies and the
# budget. These tests are adjusted accordingly; the email-regex assertions are unchanged (still
# "no address may ever appear in a committed file").


def _read(name: str) -> str:
    return (REPO / "infra" / name).read_text(encoding="utf-8")


def test_monitoring_checks_both_endpoints_and_commits_no_address():
    text = _read("monitoring_setup.sh")
    assert "ALERT_EMAIL:?" in text and "--path=\"$2\"" in text
    assert "ensure_check kirchhoff-web /" in text and "ensure_check kirchhoff-api-health /api/health" in text
    assert "uptime_check/check_passed" in text and "notificationChannels" in text
    assert re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text) is None


def test_budget_is_17600_inr_with_50_and_90_percent_alerts():
    text = _read("budget_setup.sh")
    assert "17600INR" in text and "012711-F23839-B5DB84" in text and "--filter-projects=projects/$P" in text
    assert "--threshold-rule=percent=0.5" in text and "--threshold-rule=percent=0.9" in text
    assert "billingbudgets.googleapis.com" in text
    assert re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", text) is None


def test_monitoring_accepts_alert_emails_plural_and_splits_on_commas():
    text = _read("monitoring_setup.sh")
    assert "ALERT_EMAILS" in text
    # splits the comma-separated list at run time rather than hard-coding any address
    assert re.search(r"IFS=','\s*\n?\s*read -ra \w+ <<< \"\$\{ALERT_EMAILS", text)
    # one channel is created/reused per address, matched by its email_address label
    assert "labels.email_address=" in text and "email_address=\"$addr\"" in text
    # display names are allowed to differ from "Kirchhoff alerts" ("Kirchhoff alerts (1)", etc.)
    assert "Kirchhoff alerts (" in text
    # matching must key off the label, never the display name, so no displayName filter on channel lookup
    assert "--filter=\"type=\\\"email\\\" AND labels.email_address=" in text


def test_monitoring_attaches_every_channel_to_both_policies():
    text = _read("monitoring_setup.sh")
    assert "CHANNELS_JSON" in text
    assert '"notificationChannels": $CHANNELS_JSON' in text


def test_budget_also_parses_alert_emails_and_attaches_every_channel():
    text = _read("budget_setup.sh")
    assert "ALERT_EMAILS" in text
    assert re.search(r"IFS=','\s*\n?\s*read -ra \w+ <<< \"\$\{ALERT_EMAILS", text)
    assert "labels.email_address=" in text
    assert "--notifications-rule-monitoring-notification-channels=" in text


def test_scripts_never_hardcode_a_real_recipient():
    for name in ("monitoring_setup.sh", "budget_setup.sh"):
        text = _read(name)
        assert "aws2.mehularora" not in text and "mehularora2399" not in text and "gmail.com" not in text
