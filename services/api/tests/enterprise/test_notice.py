"""The root NOTICE file names every direct dependency (issue #26, checklist item 7): a dependency added later without a notice
fails here instead of surfacing after the repository is made public."""
import json
import re
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
NOTICE = REPO / "NOTICE"


def _notice() -> str:
    assert NOTICE.is_file(), "the root NOTICE file is missing (third-party licences, issue #26)"
    return NOTICE.read_text(encoding="utf-8")


def _web_dependencies() -> list[str]:
    return sorted(json.loads((REPO / "apps/web/package.json").read_text(encoding="utf-8"))["dependencies"])


def _api_dependencies() -> list[str]:
    deps = tomllib.loads((REPO / "services/api/pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    return sorted({re.split(r"[=<>\[ ;~!]", d.strip())[0] for d in deps})


def test_every_direct_web_dependency_has_a_notice():
    text = _notice()
    missing = [d for d in _web_dependencies() if d not in text]
    assert not missing, f"apps/web dependencies without a line in NOTICE: {missing}"


def test_every_direct_api_dependency_has_a_notice():
    text = _notice()
    missing = [d for d in _api_dependencies() if d not in text]
    assert not missing, f"services/api dependencies without a line in NOTICE: {missing}"


def test_the_copyleft_choices_are_stated():
    """elkjs is EPL-2.0 OR GPL-3.0-or-later: the notice must say which one we use, and the fonts must name their licence."""
    text = " ".join(_notice().split())  # the notice wraps its lines, a phrase may span two of them
    assert "elkjs" in text and "Eclipse Public License 2.0" in text
    assert "SIL Open Font License" in text and "lucide-react" in text


def test_the_demo_world_and_engineering_labels_are_present():
    text = " ".join(_notice().split())
    assert "fictional" in text and "illustrative values" in text
