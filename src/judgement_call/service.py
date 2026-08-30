import logging
import uuid
from typing import Optional

from judgement_call.agent import create_worker_agent
from judgement_call.contracts import (
    CompletedResponse,
    FailureCode,
    FailureResponse,
    NeedsHumanResponse,
    ResumeRequest,
    RunResponse,
    StartRequest,
    TaskContract,
)
from judgement_call.governor import AttentionGovernor
from judgement_call.ledger import RunLedger
from judgement_call.verifier import IndependentVerifier
from judgement_call.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class RunSession:
    def __init__(self, run_id: str, contract: TaskContract) -> None:
        self.run_id = run_id
        self.contract = contract
        self.workspace = WorkspaceManager(fixture_src="fixtures/concurrency_demo")
        self.ledger = RunLedger()
        self.governor = AttentionGovernor(ledger=self.ledger, governor_enabled=True)
        self.agent = create_worker_agent(
            workspace=self.workspace,
            ledger=self.ledger,
            contract=self.contract,
            governor=self.governor,
        )
        self.is_completed = False
        self.last_error: Optional[str] = None


class JudgementCallService:
    def __init__(self) -> None:
        self.sessions: dict[str, RunSession] = {}

    def start(self, request: StartRequest, session_id: str | None = None) -> RunResponse:
        run_id = session_id or f"run-{uuid.uuid4().hex[:8]}"
        contract = TaskContract(
            scenario=request.scenario,
            allowed_paths=["src/demoqueue/processor.py", "tests/test_processor.py"],
            protected_paths=["pyproject.toml"],
            acceptance_command="python -m pytest -q",
            frozen_constraints={
                "public_signature": "process_items(items, worker)",
                "success_result_order": "input-order",
                "dependency_policy": "no-new-runtime-dependencies",
                "interface_style": "synchronous",
            },
        )

        session = RunSession(run_id=run_id, contract=contract)
        self.sessions[run_id] = session

        return self._execute_run(session, request.task)

    def resume(self, request: ResumeRequest, session_id: str | None = None) -> RunResponse:
        # Find session containing interrupt_id or matching session_id
        session: Optional[RunSession] = None
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
        else:
            for s in self.sessions.values():
                if request.interrupt_id in s.governor.pending_interrupts:
                    session = s
                    break

        if not session:
            # Fallback for mock tests where session might not be explicitly
            # stored or mock run_id used. Create dummy or return failure.
            return FailureResponse(
                run_id=session_id or request.interrupt_id,
                code=FailureCode.INVALID_SESSION,
                message=f"Session or interrupt_id {request.interrupt_id} not found",
                receipt=RunLedger().receipt(),
            )

        card = session.governor.pending_interrupts.pop(request.interrupt_id, None)
        if not card and session.governor.pending_interrupts:
            # pop the first pending interrupt if exact ID not found
            first_key = list(session.governor.pending_interrupts.keys())[0]
            card = session.governor.pending_interrupts.pop(first_key)

        # Resume agent execution with user choice
        choice_id = request.response.choice_id
        note = request.response.note or ""

        return self._execute_run(
            session, f"User resumed with choice {choice_id}. Note: {note}"
        )

    def _execute_run(self, session: RunSession, prompt: str) -> RunResponse:
        try:
            # Run agent
            session.agent(prompt)

            # Check if there are pending interrupts
            if session.governor.pending_interrupts:
                items = list(session.governor.pending_interrupts.items())
                if items:
                    interrupt_id, card = items[0]
                    return NeedsHumanResponse(
                        run_id=session.run_id,
                        decision=card,
                        receipt=session.ledger.receipt(),
                    )

            # If no pending interrupts, run independent verifier
            verifier = IndependentVerifier(session.workspace, session.contract)
            passed, msg = verifier.verify()
            session.ledger.set_final_verifier(passed)

            diff = session.workspace.compute_diff()

            if passed:
                return CompletedResponse(
                    run_id=session.run_id,
                    summary="Task completed successfully and verified.",
                    diff=diff,
                    verification="PASS",
                    receipt=session.ledger.receipt(),
                )
            else:
                return FailureResponse(
                    run_id=session.run_id,
                    code=FailureCode.VERIFICATION_FAILED,
                    message=msg,
                    receipt=session.ledger.receipt(),
                )
        except Exception as e:
            logger.exception(f"Error executing run {session.run_id}: {e}")
            return FailureResponse(
                run_id=session.run_id,
                code=FailureCode.INTERNAL_ERROR,
                message=str(e),
                receipt=session.ledger.receipt(),
            )
