import os

import pytest

from kirchhoff.agents.runner import AgentSpec

pytestmark = [pytest.mark.live,
              pytest.mark.skipif(os.environ.get("KIRCHHOFF_LIVE") != "1", reason="set KIRCHHOFF_LIVE=1")]

SPEC = AgentSpec(name="layout", thinking="low", timeout_s=60,
                 instruction="Call get_rack_rows exactly once, then reply with one sentence naming the rows.")


def get_rack_rows() -> dict:
    """Return the ids of the rack rows in the hall."""
    return {"rows": ["R1", "R2", "R3"]}


@pytest.mark.parametrize("mode", ["workflow", "agent"])
def test_adk_runner_calls_tool_and_narrates(mode):
    from kirchhoff.agents.adk_runner import AdkRunner

    res = AdkRunner(mode=mode).run(SPEC, "live", "Which rows are in the hall?", tools=[get_rack_rows])
    assert [c.name for c in res.tool_calls] == ["get_rack_rows"]
    assert "R1" in res.text and res.tokens_in > 0


def test_genai_runner_calls_tool_and_narrates():
    from kirchhoff.agents.genai_runner import GenaiRunner

    res = GenaiRunner().run(SPEC, "live", "Which rows are in the hall?", tools=[get_rack_rows])
    assert [c.name for c in res.tool_calls] == ["get_rack_rows"]
    assert "R1" in res.text


def test_medium_thinking_level_is_accepted():
    from kirchhoff.agents.genai_runner import GenaiRunner

    spec = AgentSpec(name="power", thinking="medium", timeout_s=60, instruction="Reply with the word ok.")
    assert GenaiRunner().run(spec, "live", "Say ok.").text
