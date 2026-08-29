from strands import Agent, tool
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

    class MockEvent:
        tool_name = "request_decision"
        tool_args = {
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

    action = governor.before_tool_call(MockEvent())
    assert action.type == "confirm"
    assert ledger.receipt().auto_resolved == 1


def test_governor_evidence_check_guide():
    ledger = RunLedger()
    governor = AttentionGovernor(ledger=ledger, governor_enabled=True)

    class MockEvent:
        tool_name = "request_decision"
        tool_args = {
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

    action = governor.before_tool_call(MockEvent())
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

    class MockEvent:
        tool_name = "request_decision"
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

    action = governor.before_tool_call(MockEvent())
    assert action.type == "confirm"
    assert ledger.receipt().human_interrupts == 1
    assert len(governor.pending_interrupts) == 1


def test_governor_baseline_mode():
    ledger = RunLedger()
    governor = AttentionGovernor(
        ledger=ledger,
        governor_enabled=False,
    )

    class MockEvent:
        tool_name = "request_decision"
        tool_args = {
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

    action = governor.before_tool_call(MockEvent())
    assert action.type == "confirm"
    assert ledger.receipt().human_interrupts == 1
    assert "Baseline mode" in governor.pending_interrupts["int-1"].why_human


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
