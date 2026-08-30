import pytest
from strands import Agent, tool
from strands.interrupt import Interrupt, InterruptException
from strands.types.tools import ToolUse
from strands.vended_interventions.cedar import CedarAuthorization

from judgement_call.contracts import (
    DecisionOption,
    DecisionProposal,
    Dimensions,
    GateDecision,
    Impact,
)
from judgement_call.gate import GateDecider, StrandsGateDecider
from judgement_call.governor import AttentionGovernor
from judgement_call.ledger import RunLedger


@tool
def list_tree() -> str:
    return "."


@tool
def read_text(path: str) -> str:
    return "content"


@tool
def search_text(pattern: str) -> str:
    return "match"


@tool
def write_text(path: str, content: str) -> str:
    return "written"


@tool
def run_tests() -> str:
    return "passed"


@tool
def request_decision(
    question: str,
    options: list[dict],
    recommendation: str,
    dimensions: list[str],
    impact: str,
    reversible: bool,
    evidence: str,
) -> str:
    return recommendation


@tool
def unauthorized_tool() -> str:
    return "unauthorized"


class MockGateDecider:
    def __init__(self, decision: GateDecision) -> None:
        self.decision = decision

    def decide(self, proposal: DecisionProposal) -> GateDecision:
        return self.decision


class RawInterruptEvent:
    def __init__(self, tool_args: dict, response=None, interrupt_id="raw-int-1"):
        self.tool_name = "request_decision"
        self.tool_args = tool_args
        self.tool_use = {"name": self.tool_name, "input": tool_args, "toolUseId": "tool-1"}
        self.response = response
        self.interrupt_id = interrupt_id

    def interrupt(self, name: str, reason: str):
        if self.response is not None:
            return self.response
        raise InterruptException(Interrupt(self.interrupt_id, name, reason))


def test_gate_decider_protocol():
    decider = StrandsGateDecider()
    assert isinstance(decider, GateDecider)

    proposal = DecisionProposal(
        question="Which algorithm?",
        options=[
            DecisionOption(id="A", label="A", consequence="A"),
            DecisionOption(id="B", label="B", consequence="B"),
        ],
        recommendation="A",
        dimensions=[Dimensions.IMPLEMENTATION.value],
        impact=Impact.LOW.value,
        reversible=True,
        evidence="Evidence text",
    )
    res = decider.decide(proposal)
    assert res.action == "AUTO_RESOLVE"


def test_governor_deterministic_auto_resolve():
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=True)

    event = RawInterruptEvent(
        {
            "question": "Use async?",
            "options": [
                {"id": "A", "label": "Yes", "consequence": "Fast"},
                {"id": "B", "label": "No", "consequence": "Slow"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.IMPLEMENTATION.value],
            "impact": Impact.LOW.value,
            "reversible": True,
            "evidence": "Benchmark shows 2x speedup",
        }
    )

    action = governor.before_tool_call(event)
    assert action.type == "guide"
    assert "choice 'A'" in action.feedback
    assert ledger.receipt().auto_resolved == 1


@pytest.mark.parametrize("impact", [Impact.LOW.value, Impact.MEDIUM.value])
def test_governor_deterministic_implementation_only_allows_low_and_medium(impact):
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=True)
    event = RawInterruptEvent(
        {
            "question": "Use a private helper?",
            "options": [
                {"id": "A", "label": "Use helper", "consequence": "Internal cleanup"},
                {"id": "B", "label": "Keep inline", "consequence": "No change"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.IMPLEMENTATION.value],
            "impact": impact,
            "reversible": True,
            "evidence": "The helper is private and the change is reversible.",
        }
    )

    action = governor.before_tool_call(event)

    assert action.type == "guide"
    assert ledger.receipt().auto_resolved == 1


def test_governor_matching_frozen_constraint_auto_resolves():
    ledger = RunLedger()
    governor = AttentionGovernor(
        ledger=ledger,
        governor_enabled=True,
        frozen_constraints={"public_signature": "process_items(items, worker)"},
    )
    event = RawInterruptEvent(
        {
            "question": "Which signature should remain?",
            "options": [
                {"id": "A", "label": "Keep frozen signature", "consequence": "Compatibility"},
                {"id": "B", "label": "Change signature", "consequence": "Breaks callers"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.PUBLIC_BEHAVIOR.value],
            "impact": Impact.MEDIUM.value,
            "reversible": True,
            "constraint_key": "public_signature",
            "evidence": "The frozen public_signature constraint determines the choice.",
        }
    )

    action = governor.before_tool_call(event)

    assert action.type == "guide"
    assert "choice 'A'" in action.feedback
    assert ledger.receipt().auto_resolved == 1


@pytest.mark.parametrize(
    "dimension",
    [
        Dimensions.EXTERNAL_SIDE_EFFECT.value,
        Dimensions.SECURITY.value,
        Dimensions.DATA.value,
        Dimensions.PUBLIC_BEHAVIOR.value,
    ],
)
def test_unresolved_material_dimensions_use_gate(dimension):
    ledger = RunLedger()
    mock_gate = MockGateDecider(
        GateDecision(
            action="ASK_HUMAN",
            choice_id=None,
            reason="Gate review required",
        )
    )
    governor = AttentionGovernor(
        ledger=ledger,
        gate_decider=mock_gate,
        governor_enabled=True,
    )
    event = RawInterruptEvent(
        {
            "question": "Choose a material option",
            "options": [
                {"id": "A", "label": "Option A", "consequence": "Material effect"},
                {"id": "B", "label": "Option B", "consequence": "Different effect"},
            ],
            "recommendation": "A",
            "dimensions": [dimension],
            "impact": Impact.LOW.value,
            "reversible": True,
            "evidence": "Repository evidence is insufficient to resolve this safely.",
        }
    )

    with pytest.raises(InterruptException):
        governor.before_tool_call(event)

    assert ledger.receipt().human_interrupts == 1


def test_gate_agent_invalid_output_fails_closed_to_ask_human():
    proposal = DecisionProposal(
        question="Which option?",
        options=[
            DecisionOption(id="A", label="A", consequence="A"),
            DecisionOption(id="B", label="B", consequence="B"),
        ],
        recommendation="A",
        dimensions=[Dimensions.SECURITY.value],
        impact=Impact.HIGH.value,
        reversible=False,
        evidence="Security evidence",
    )
    decider = StrandsGateDecider(agent=lambda prompt: '{"action":"MAYBE"}')

    result = decider.decide(proposal)

    assert result.action == "ASK_HUMAN"


def test_governor_evidence_check_guide():
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=True)

    event = RawInterruptEvent(
        {
            "question": "Use async?",
            "options": [
                {"id": "A", "label": "Yes", "consequence": "Fast"},
                {"id": "B", "label": "No", "consequence": "Slow"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.IMPLEMENTATION.value],
            "impact": Impact.LOW.value,
            "reversible": True,
            "evidence": "",  # Empty evidence triggers Guide
        }
    )

    action = governor.before_tool_call(event)
    assert action.type == "guide"
    assert "missing required evidence" in action.feedback


def test_governor_gate_routing_ask_human():
    ledger = RunLedger()
    mock_gate = MockGateDecider(
        GateDecision(
            action="ASK_HUMAN",
            choice_id=None,
            reason="Ambiguous public behavior tradeoff",
        )
    )
    governor = AttentionGovernor(
        ledger=ledger,
        gate_decider=mock_gate,
        governor_enabled=True,
    )

    event = RawInterruptEvent(
        {
            "question": "Change public API signature?",
            "options": [
                {"id": "A", "label": "Yes", "consequence": "Breaking"},
                {"id": "B", "label": "No", "consequence": "Safe"},
            ],
            "recommendation": "B",
            "dimensions": [Dimensions.PUBLIC_BEHAVIOR.value],
            "impact": Impact.HIGH.value,
            "reversible": False,
            "evidence": "Public contract requirement",
        }
    )

    with pytest.raises(InterruptException):
        governor.before_tool_call(event)

    assert ledger.receipt().human_interrupts == 1
    assert len(governor.pending_interrupts) == 1


def test_governor_raw_interrupt_resume_returns_proceed_and_applies_choice():
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=True)
    tool_args = {
        "question": "Change public API signature?",
        "options": [
            {"id": "A", "label": "Yes", "consequence": "Breaking"},
            {"id": "B", "label": "No", "consequence": "Safe"},
        ],
        "recommendation": "B",
        "dimensions": [Dimensions.PUBLIC_BEHAVIOR.value],
        "impact": Impact.HIGH.value,
        "reversible": False,
        "evidence": "Public contract requirement",
    }

    with pytest.raises(InterruptException):
        governor.before_tool_call(RawInterruptEvent(tool_args))

    resumed = RawInterruptEvent(tool_args, response="A")
    action = governor.before_tool_call(resumed)

    assert action.type == "proceed"
    assert tool_args["recommendation"] == "A"
    assert ledger.receipt().human_interrupts == 1


def test_governor_baseline_mode():
    ledger = RunLedger()
    governor = AttentionGovernor(
        ledger=ledger,
        governor_enabled=False,
    )

    event = RawInterruptEvent(
        {
            "question": "Simple choice",
            "options": [
                {"id": "A", "label": "A", "consequence": "A"},
                {"id": "B", "label": "B", "consequence": "B"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.IMPLEMENTATION.value],
            "impact": Impact.LOW.value,
            "reversible": True,
            "evidence": "Some evidence",
        }
    )

    with pytest.raises(InterruptException):
        governor.before_tool_call(event)
    assert ledger.receipt().human_interrupts == 1
    assert "Baseline mode" in next(iter(governor.pending_interrupts.values())).why_human


def test_inadequate_evidence_is_guided_even_in_baseline_mode():
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=False)
    event = RawInterruptEvent(
        {
            "question": "Choose an option",
            "options": [
                {"id": "A", "label": "A", "consequence": "A"},
                {"id": "B", "label": "B", "consequence": "B"},
            ],
            "recommendation": "A",
            "dimensions": [Dimensions.IMPLEMENTATION.value],
            "impact": Impact.LOW.value,
            "reversible": True,
            "evidence": "",
        }
    )

    action = governor.before_tool_call(event)

    assert action.type == "guide"
    assert ledger.receipt().human_interrupts == 0


def test_cedar_authorization_policy():
    cedar = CedarAuthorization(
        policies="policies/agent.cedar",
        tools=[
            list_tree.tool_spec,
            read_text.tool_spec,
            search_text.tool_spec,
            write_text.tool_spec,
            run_tests.tool_spec,
            request_decision.tool_spec,
            unauthorized_tool.tool_spec,
        ],
    )

    agent_inst = Agent(
        tools=[list_tree],
        interventions=[cedar],
    )

    t_use = ToolUse(name="list_tree", input={}, toolUseId="tu-1")

    class MockEvent:
        agent = agent_inst
        selected_tool = list_tree
        tool_use = t_use
        invocation_state = {}

    res = cedar.before_tool_call(MockEvent())
    assert res.type == "proceed"

    unauthorized_use = ToolUse(name="unauthorized_tool", input={}, toolUseId="tu-2")

    class MockDeniedEvent:
        agent = agent_inst
        selected_tool = unauthorized_tool
        tool_use = unauthorized_use
        invocation_state = {}

    res_denied = cedar.before_tool_call(MockDeniedEvent())
    assert res_denied.type == "deny"
