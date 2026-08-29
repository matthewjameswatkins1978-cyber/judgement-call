import pytest
from pydantic import ValidationError

from judgement_call.contracts import (
    AttentionReceipt,
    DecisionCard,
    DecisionOption,
    DecisionProposal,
    Dimensions,
    GateDecision,
    Impact,
    ResumeChoice,
    ResumeRequest,
    Scenario,
    StartRequest,
)
from judgement_call.ledger import RunLedger


def test_start_request_valid():
    req = StartRequest(
        op="start",
        scenario="concurrency-demo",
        task="Make process_items execute concurrently",
    )
    assert req.op == "start"
    assert req.scenario == Scenario.CONCURRENCY_DEMO
    assert req.task == "Make process_items execute concurrently"


def test_start_request_invalid_scenario():
    with pytest.raises(ValidationError):
        StartRequest(op="start", scenario="invalid-scenario", task="test")


def test_resume_request_valid():
    req = ResumeRequest(
        op="resume",
        interrupt_id="123",
        response=ResumeChoice(choice_id="opt-1", note="looks good"),
    )
    assert req.op == "resume"
    assert req.interrupt_id == "123"
    assert req.response.choice_id == "opt-1"
    assert req.response.note == "looks good"


def test_decision_proposal_valid():
    proposal = DecisionProposal(
        question="Should we use asyncio?",
        options=[
            DecisionOption(id="A", label="Yes", consequence="Faster"),
            DecisionOption(id="B", label="No", consequence="Slower"),
        ],
        recommendation="A",
        dimensions=[Dimensions.IMPLEMENTATION.value, Dimensions.PUBLIC_BEHAVIOR.value],
        impact=Impact.LOW.value,
        reversible=True,
        evidence="Some evidence",
    )
    assert len(proposal.options) == 2
    assert proposal.impact == "low"


def test_decision_proposal_reject_too_few_options():
    with pytest.raises(ValidationError, match="between 2 and 4 items"):
        DecisionProposal(
            question="Q?",
            options=[DecisionOption(id="A", label="Only one", consequence="None")],
            recommendation="A",
            dimensions=[Dimensions.IMPLEMENTATION.value],
            impact=Impact.LOW.value,
            reversible=True,
            evidence="Ev",
        )


def test_decision_proposal_reject_too_many_options():
    with pytest.raises(ValidationError, match="between 2 and 4 items"):
        DecisionProposal(
            question="Q?",
            options=[
                DecisionOption(id="1", label="1", consequence="1"),
                DecisionOption(id="2", label="2", consequence="2"),
                DecisionOption(id="3", label="3", consequence="3"),
                DecisionOption(id="4", label="4", consequence="4"),
                DecisionOption(id="5", label="5", consequence="5"),
            ],
            recommendation="1",
            dimensions=[Dimensions.IMPLEMENTATION.value],
            impact=Impact.LOW.value,
            reversible=True,
            evidence="Ev",
        )


def test_decision_proposal_invalid_impact():
    with pytest.raises(ValidationError, match="Invalid impact"):
        DecisionProposal(
            question="Q?",
            options=[
                DecisionOption(id="A", label="A", consequence="A"),
                DecisionOption(id="B", label="B", consequence="B"),
            ],
            recommendation="A",
            dimensions=[Dimensions.IMPLEMENTATION.value],
            impact="super-high",
            reversible=True,
            evidence="Ev",
        )


def test_decision_proposal_invalid_dimension():
    with pytest.raises(ValidationError, match="Invalid dimension"):
        DecisionProposal(
            question="Q?",
            options=[
                DecisionOption(id="A", label="A", consequence="A"),
                DecisionOption(id="B", label="B", consequence="B"),
            ],
            recommendation="A",
            dimensions=["invalid-dimension"],
            impact=Impact.LOW.value,
            reversible=True,
            evidence="Ev",
        )


def test_gate_decision_valid():
    gd = GateDecision(action="AUTO_RESOLVE", choice_id="A", reason="Clear choice")
    assert gd.action == "AUTO_RESOLVE"
    assert gd.choice_id == "A"


def test_decision_card_valid():
    card = DecisionCard(
        interrupt_id="int-1",
        question="Which strategy?",
        why_human="Ambiguous trade-off",
        options=[
            DecisionOption(id="A", label="A", consequence="A"),
            DecisionOption(id="B", label="B", consequence="B"),
        ],
        recommendation="A",
        evidence="Ev",
    )
    assert card.interrupt_id == "int-1"
    assert len(card.options) == 2


def test_run_ledger_counters():
    ledger = RunLedger()

    ledger.record_tool_call()
    ledger.record_tool_call()
    ledger.record_decision_proposal()
    ledger.record_auto_resolve()
    ledger.record_human_interrupt()
    ledger.record_policy_denial()
    ledger.record_test_run()
    ledger.set_final_verifier(True)

    receipt = ledger.receipt()
    assert isinstance(receipt, AttentionReceipt)
    assert receipt.tool_calls == 2
    assert receipt.decision_proposals == 1
    assert receipt.auto_resolved == 1
    assert receipt.human_interrupts == 1
    assert receipt.policy_denials == 1
    assert receipt.test_runs == 1
    assert receipt.final_verifier_passed is True


def test_run_ledger_session_scoped():
    ledger1 = RunLedger()
    ledger2 = RunLedger()

    ledger1.record_tool_call()
    assert ledger1.receipt().tool_calls == 1
    assert ledger2.receipt().tool_calls == 0
