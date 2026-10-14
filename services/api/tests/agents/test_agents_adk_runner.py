"""Offline regression test (Task 11 fix round 1): AdkRunner._node must build the LlmAgent with a callable
instruction, not a bare str. A bare str instruction containing a literal "{value}"/"{limit}" placeholder
(every NUMBERS_RULE-bearing spec in agents/specs.py has one) is run through ADK's inject_session_state()
and raises KeyError on every real call -- this is exactly the bug fixed in commit 6f2725a. Makes no network
call: it only inspects the node ADK builds, never runs it."""
from google.adk.agents import LlmAgent
from google.adk.workflow import Workflow

from kirchhoff.agents.adk_runner import AdkRunner
from kirchhoff.agents.runner import AgentSpec

SPEC = AgentSpec(name="orchestrator", instruction="Use the placeholder {limit} for numbers.", thinking="low")


def _llm_agent(node):
    """The LlmAgent itself in agent mode, or the one LlmAgent inside the Workflow's edges in workflow mode."""
    if isinstance(node, Workflow):
        (start, agent), = node.edges
        return agent
    return node


def test_agent_mode_instruction_is_callable_and_verbatim():
    agent = _llm_agent(AdkRunner(mode="agent")._node(SPEC, []))
    assert isinstance(agent, LlmAgent)
    assert not isinstance(agent.instruction, str) and callable(agent.instruction)
    assert agent.instruction(None) == SPEC.instruction


def test_workflow_mode_instruction_is_callable_and_verbatim():
    node = AdkRunner(mode="workflow")._node(SPEC, [])
    assert isinstance(node, Workflow)
    agent = _llm_agent(node)
    assert isinstance(agent, LlmAgent)
    assert not isinstance(agent.instruction, str) and callable(agent.instruction)
    assert agent.instruction(None) == SPEC.instruction
