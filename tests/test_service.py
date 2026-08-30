from unittest.mock import MagicMock, patch

from judgement_call.contracts import (
    CompletedResponse,
    DecisionCard,
    DecisionOption,
    FailureCode,
    FailureResponse,
    NeedsHumanResponse,
    ResumeRequest,
    StartRequest,
    TaskContract,
)
from judgement_call.ledger import RunLedger
from judgement_call.service import JudgementCallService, RunSession


def test_service_start_creates_session_and_contract():
    service = JudgementCallService()
    req = StartRequest(
        op="start",
        scenario="concurrency-demo",
        task="Implement concurrent processing",
    )

    with patch("judgement_call.service.RunSession") as MockRunSession:
        mock_session_instance = MockRunSession.return_value
        mock_session_instance.run_id = "session-abc"
        mock_session_instance.contract = TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[
                "src/demoqueue/processor.py",
                "tests/test_processor.py",
            ],
            protected_paths=["pyproject.toml"],
            acceptance_command="python -m pytest -q",
            frozen_constraints={},
        )
        mock_session_instance.agent.return_value = "Agent finished"
        mock_session_instance.ledger = RunLedger()
        mock_session_instance.workspace = MagicMock()
        mock_session_instance.workspace.compute_diff.return_value = "diff content"

        with patch("judgement_call.service.IndependentVerifier.verify") as mock_verify:
            mock_verify.return_value = (True, "All tests passed")

            resp = service.start(req, session_id="session-abc")

            assert isinstance(resp, CompletedResponse)
            assert resp.run_id == "session-abc"
            assert "session-abc" in service.sessions


def test_service_pause_interrupt_returns_decision_card():
    service = JudgementCallService()

    session_id = "session-interrupt"
    session = RunSession(
        run_id=session_id,
        contract=TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[],
            protected_paths=[],
            acceptance_command="pytest",
            frozen_constraints={},
        ),
    )

    card = DecisionCard(
        interrupt_id="int-999",
        question="Which execution model?",
        why_human="High impact tradeoff",
        options=[
            DecisionOption(id="A", label="AsyncIO", consequence="Fast"),
            DecisionOption(id="B", label="Threads", consequence="Simple"),
        ],
        recommendation="A",
        evidence="Benchmark data",
    )
    session.governor.pending_interrupts["int-999"] = card
    service.sessions[session_id] = session

    with patch.object(session, "agent"):
        resp = service._execute_run(session, "run prompt")
        assert isinstance(resp, NeedsHumanResponse)
        assert resp.run_id == session_id
        assert resp.decision.interrupt_id == "int-999"


def test_service_resume_maps_choice_id():
    service = JudgementCallService()
    session_id = "session-resume"
    session = RunSession(
        run_id=session_id,
        contract=TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[],
            protected_paths=[],
            acceptance_command="pytest",
            frozen_constraints={},
        ),
    )
    card = DecisionCard(
        interrupt_id="int-123",
        question="Which model?",
        why_human="Tradeoff",
        options=[DecisionOption(id="A", label="A", consequence="A")],
        recommendation="A",
        evidence="Ev",
    )
    session.governor.pending_interrupts["int-123"] = card
    service.sessions[session_id] = session

    resume_req = ResumeRequest(
        op="resume",
        interrupt_id="int-123",
        response={"choice_id": "A", "note": "Proceeding with A"},
    )

    with patch.object(session, "agent") as mock_agent:
        mock_agent.return_value = "Resumed successfully"
        with patch("judgement_call.service.IndependentVerifier.verify") as mock_verify:
            mock_verify.return_value = (True, "Passed")

            resp = service.resume(resume_req, session_id=session_id)
            assert isinstance(resp, CompletedResponse)
            assert resp.run_id == session_id
            mock_agent.assert_called_once()
            assert mock_agent.call_args[0][0] == [
                {
                    "interruptResponse": {
                        "interruptId": "int-123",
                        "response": "A",
                    }
                }
            ]


def test_service_same_session_id_preserved():
    service = JudgementCallService()
    req = StartRequest(op="start", scenario="concurrency-demo", task="Task")

    with patch("judgement_call.service.RunSession") as MockRunSession:
        mock_session_instance = MockRunSession.return_value
        mock_session_instance.run_id = "my-persistent-session"
        mock_session_instance.contract = TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[],
            protected_paths=[],
            acceptance_command="pytest",
            frozen_constraints={},
        )
        mock_session_instance.agent.return_value = "Done"
        mock_session_instance.ledger = RunLedger()
        mock_session_instance.workspace = MagicMock()
        mock_session_instance.workspace.compute_diff.return_value = "diff content"

        with patch("judgement_call.service.IndependentVerifier.verify") as mock_verify:
            mock_verify.return_value = (True, "OK")

            resp1 = service.start(req, session_id="my-persistent-session")
            assert resp1.run_id == "my-persistent-session"

            resume_req = ResumeRequest(
                op="resume",
                interrupt_id="int-123",
                response={"choice_id": "A"},
            )
            session = service.sessions["my-persistent-session"]
            session.governor.pending_interrupts["int-123"] = DecisionCard(
                interrupt_id="int-123",
                question="Q?",
                why_human="Why",
                options=[DecisionOption(id="A", label="A", consequence="A")],
                recommendation="A",
                evidence="Ev",
            )
            resp2 = service.resume(resume_req, session_id="my-persistent-session")
            assert resp2.run_id == "my-persistent-session"
            assert "my-persistent-session" in service.sessions


def test_service_attention_receipt_counters_survive_pause_resume():
    service = JudgementCallService()
    session_id = "session-counters"
    session = RunSession(
        run_id=session_id,
        contract=TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[],
            protected_paths=[],
            acceptance_command="pytest",
            frozen_constraints={},
        ),
    )
    session.ledger.record_auto_resolve()
    session.ledger.record_auto_resolve()
    session.ledger.record_human_interrupt()

    card = DecisionCard(
        interrupt_id="int-counters",
        question="Q?",
        why_human="Why",
        options=[DecisionOption(id="A", label="A", consequence="A")],
        recommendation="A",
        evidence="Ev",
    )
    session.governor.pending_interrupts["int-counters"] = card
    service.sessions[session_id] = session

    receipt_before = session.ledger.receipt()
    assert receipt_before.auto_resolved == 2
    assert receipt_before.human_interrupts == 1

    resume_req = ResumeRequest(
        op="resume",
        interrupt_id="int-counters",
        response={"choice_id": "A"},
    )
    with patch.object(session, "agent") as mock_agent:
        mock_agent.return_value = "Resumed"
        with patch("judgement_call.service.IndependentVerifier.verify") as mock_verify:
            mock_verify.return_value = (True, "OK")

            resp = service.resume(resume_req, session_id=session_id)
            assert isinstance(resp, CompletedResponse)
            receipt_after = session.ledger.receipt()
            assert receipt_after.auto_resolved == 2
            assert receipt_after.human_interrupts == 1


def test_service_independent_verifier_failure_returns_verification_failed():
    service = JudgementCallService()
    req = StartRequest(
        op="start", scenario="concurrency-demo", task="Faulty task"
    )

    with patch("judgement_call.service.RunSession") as MockRunSession:
        mock_session_instance = MockRunSession.return_value
        mock_session_instance.run_id = "session-fail"
        mock_session_instance.contract = TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[],
            protected_paths=[],
            acceptance_command="pytest",
            frozen_constraints={},
        )
        mock_session_instance.agent.return_value = "Agent done"
        mock_session_instance.ledger = RunLedger()
        mock_session_instance.workspace = MagicMock()
        mock_session_instance.workspace.compute_diff.return_value = "diff content"

        with patch("judgement_call.service.IndependentVerifier.verify") as mock_verify:
            mock_verify.return_value = (False, "AssertionError in tests")

            resp = service.start(req, session_id="session-fail")
            assert isinstance(resp, FailureResponse)
            assert resp.code == FailureCode.VERIFICATION_FAILED
            assert "AssertionError" in resp.message
