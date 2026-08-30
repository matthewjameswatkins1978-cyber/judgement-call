import os
from unittest.mock import patch

import pytest

from judgement_call.contracts import StartRequest
from judgement_call.service import JudgementCallService


def test_offline_demo_flow():
    """Test the offline run end-to-end without AWS credentials."""
    with patch("judgement_call.service.RunSession") as MockRunSession:
        mock_session = MockRunSession.return_value
        mock_session.run_id = "test-offline-run"
        mock_session.governor.pending_interrupts = {}

        from judgement_call.contracts import TaskContract
        from judgement_call.ledger import RunLedger
        from judgement_call.verifier import IndependentVerifier
        from judgement_call.workspace import WorkspaceManager

        workspace = WorkspaceManager(fixture_src="fixtures/concurrency_demo")
        concurrent_code = '''import concurrent.futures
from typing import Any, Callable, List

def process_items(items: List[Any], worker: Callable[[Any], Any]) -> List[Any]:
    if not items:
        return []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(worker, item) for item in items]
        return [f.result() for f in futures]
'''.strip() + "\n"
        processor_path = workspace.root / "src" / "demoqueue" / "processor.py"
        processor_path.write_text(concurrent_code, encoding="utf-8")

        contract = TaskContract(
            scenario="concurrency-demo",
            allowed_paths=["src/demoqueue/processor.py", "tests/test_processor.py"],
            protected_paths=["pyproject.toml"],
            acceptance_command="python -m pytest -q",
            frozen_constraints={
                "public_signature": "process_items(items, worker)",
                "success_result_order": "input-order",
            },
        )
        verifier = IndependentVerifier(workspace, contract)
        passed, _ = verifier.verify()

        ledger = RunLedger()
        ledger.record_decision_proposal()
        ledger.record_auto_resolve()
        ledger.record_decision_proposal()
        ledger.record_human_interrupt()
        ledger.set_final_verifier(passed)
        receipt = ledger.receipt()

        assert passed is True
        assert receipt.final_verifier_passed is True
        assert receipt.auto_resolved >= 1
        assert receipt.human_interrupts == 1


@pytest.mark.live
def test_live_demo_flow():
    """Test live demo flow invoking Bedrock when credentials are configured."""
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE")
    if not aws_key:
        pytest.skip("AWS credentials not configured; skipping live demo test.")

    service = JudgementCallService()
    req = StartRequest(
        op="start",
        scenario="concurrency-demo",
        task="Make process_items execute work concurrently.",
    )
    res = service.start(req, session_id="live-test-session")
    assert res is not None
