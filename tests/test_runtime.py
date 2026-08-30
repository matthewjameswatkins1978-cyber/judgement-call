from unittest.mock import patch

from bedrock_agentcore import BedrockAgentCoreContext

from judgement_call.contracts import (
    AttentionReceipt,
    CompletedResponse,
    DecisionCard,
    DecisionOption,
    NeedsHumanResponse,
)
from judgement_call.runtime import app, handle_agent_request


def test_runtime_app_instance():
    assert app is not None
    assert "main" in app.handlers


@patch("judgement_call.service.JudgementCallService.start")
def test_runtime_start_invocation(mock_start):
    mock_start.return_value = CompletedResponse(
        run_id="test-run-1",
        summary="Success",
        diff="diff",
        verification="PASS",
        receipt=AttentionReceipt(final_verifier_passed=True),
    )

    BedrockAgentCoreContext.set_request_context(request_id="req-1", session_id="session-xyz")

    payload = {
        "op": "start",
        "scenario": "concurrency-demo",
        "task": "Test task",
    }

    res = handle_agent_request(payload)
    assert res["status"] == "completed"
    assert res["run_id"] == "test-run-1"
    mock_start.assert_called_once()
    # Verify session_id from context was passed
    _, kwargs = mock_start.call_args
    assert kwargs.get("session_id") == "session-xyz"


@patch("judgement_call.service.JudgementCallService.resume")
def test_runtime_resume_invocation(mock_resume):
    mock_resume.return_value = NeedsHumanResponse(
        run_id="test-run-2",
        decision=DecisionCard(
            interrupt_id="int-456",
            question="Choice?",
            why_human="Why",
            options=[DecisionOption(id="A", label="A", consequence="A")],
            recommendation="A",
            evidence="Ev",
        ),
        receipt=AttentionReceipt(),
    )

    BedrockAgentCoreContext.set_request_context(request_id="req-2", session_id="session-abc")

    payload = {
        "op": "resume",
        "interrupt_id": "int-456",
        "response": {"choice_id": "A", "note": "Note"},
    }

    res = handle_agent_request(payload)
    assert res["status"] == "needs_human"
    assert res["decision"]["interrupt_id"] == "int-456"
    mock_resume.assert_called_once()
    _, kwargs = mock_resume.call_args
    assert kwargs.get("session_id") == "session-abc"


@patch("judgement_call.service.JudgementCallService.start")
def test_runtime_exception_handling(mock_start):
    mock_start.side_effect = Exception("Service error")

    BedrockAgentCoreContext.set_request_context(request_id="req-3", session_id="session-err")

    payload = {
        "op": "start",
        "scenario": "concurrency-demo",
        "task": "Err task",
    }

    res = handle_agent_request(payload)
    assert res["status"] == "failed"
    assert res["code"] == "INTERNAL_ERROR"
    assert "Service error" in res["message"]
