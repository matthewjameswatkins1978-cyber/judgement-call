#!/usr/bin/env python3
import argparse
import json

from judgement_call.contracts import (
    NeedsHumanResponse,
    ResumeRequest,
    StartRequest,
)
from judgement_call.service import JudgementCallService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local Judgement Call demo (offline or live mode)."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        default=True,
        help=(
            "Run in offline simulation mode without AWS "
            "credentials (default)"
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run in live mode invoking Bedrock when "
            "credentials are configured"
        ),
    )
    parser.add_argument(
        "--session-id",
        default="demo-session-1",
        help="Session ID for the run",
    )
    parser.add_argument(
        "--task",
        default=(
            "Make process_items() execute work concurrently using "
            "concurrent.futures with signature and input order preserved."
        ),
        help="Task description",
    )

    args = parser.parse_args()

    offline_mode = not args.live

    print(
        "Starting Judgement Call Local Demo "
        f"(Mode: {'OFFLINE' if offline_mode else 'LIVE'})..."
    )
    print(f"Session ID: {args.session_id}")
    print(f"Task: {args.task}\n")

    service = JudgementCallService()

    if offline_mode:
        # In offline mode, we simulate/execute the concurrency-demo workflow:
        # - Worker inspects workspace.
        # - Surfaces an internal/reversible decision auto-resolved by Governor.
        # - Modifies processor.py to execute concurrently using concurrent.futures.
        # - Encounters an unresolved material choice producing a Decision Card.
        # - Resumes with choice 'A'.
        # - Executes the IndependentVerifier.
        # - Prints completed status with diff and Attention Receipt.

        print("[OFFLINE DEMO SIMULATION]")
        print(
            "1. Initializing workspace and agent session for "
            "scenario 'concurrency-demo'..."
        )

        from judgement_call.contracts import (
            DecisionCard,
            DecisionOption,
            TaskContract,
        )
        from judgement_call.ledger import RunLedger
        from judgement_call.verifier import IndependentVerifier
        from judgement_call.workspace import WorkspaceManager

        print("2. Worker inspecting workspace...")
        workspace = WorkspaceManager(fixture_src="fixtures/concurrency_demo")
        files = [
            str(p.relative_to(workspace.root))
            for p in workspace.root.glob("**/*")
            if p.is_file() and ".git" not in p.parts
        ]
        print(f"   Files in workspace: {files}")

        print(
            "3. Attention Governor auto-resolving internal/reversible "
            "decision (auto_resolved >= 1)..."
        )
        ledger = RunLedger()
        ledger.record_decision_proposal()
        ledger.record_auto_resolve()

        print(
            "4. Modifying src/demoqueue/processor.py to execute "
            "concurrently using concurrent.futures..."
        )
        processor_path = workspace.root / "src" / "demoqueue" / "processor.py"
        print(f"   Reading {processor_path}...")
        original_code = processor_path.read_text(encoding="utf-8")
        print(f"   Original code snippet:\n{original_code[:200]}...")

        new_processor_code = '''import concurrent.futures
from typing import Any, Callable, List

def process_items(items: List[Any], worker: Callable[[Any], Any]) -> List[Any]:
    \"\"\"Process items concurrently using concurrent.futures while preserving input order.\"\"\"
    if not items:
        return []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(worker, item) for item in items]
        results = [future.result() for future in futures]
    return results
'''.strip() + "\n"

        processor_path.write_text(new_processor_code, encoding="utf-8")
        print("   Wrote concurrent implementation to src/demoqueue/processor.py.")

        print(
            "5. Encountering unresolved material choice (failure semantics) "
            "producing a Decision Card (human_interrupts == 1)..."
        )
        ledger.record_decision_proposal()
        ledger.record_human_interrupt()
        decision_card = DecisionCard(
            interrupt_id="int-offline-1",
            question=(
                "Error handling strategy for worker exceptions "
                "during concurrent batch execution?"
            ),
            why_human="High impact architectural choice on error semantics.",
            options=[
                DecisionOption(
                    id="A",
                    label="Propagate exceptions immediately (fail fast)",
                    consequence="Fails test on first error"
                ),
                DecisionOption(
                    id="B",
                    label="Swallow and return None",
                    consequence="Silently ignores errors"
                )
            ],
            recommendation="A",
            evidence="Material architectural tradeoff requiring human review."
        )

        print("\n=== DECISION CARD PRESENTED (Human Interrupt Required) ===")
        print(json.dumps(decision_card.model_dump(), indent=2))

        print("\n6. Resuming with choice 'A'...")

        print("7. Executing the IndependentVerifier...")
        contract = TaskContract(
            scenario="concurrency-demo",
            allowed_paths=[
                "src/demoqueue/processor.py",
                "tests/test_processor.py"
            ],
            protected_paths=["pyproject.toml"],
            acceptance_command="python -m pytest -q",
            frozen_constraints={
                "public_signature": "process_items(items, worker)",
                "success_result_order": "input-order",
                "dependency_policy": "no-new-runtime-dependencies",
                "interface_style": "synchronous",
            },
        )
        verifier = IndependentVerifier(workspace, contract)
        passed, msg = verifier.verify()
        ledger.set_final_verifier(passed)
        print(f"   Verifier result: passed={passed}, message={msg}")

        diff = workspace.compute_diff()
        receipt = ledger.receipt()

        print("\n=== COMPLETED STATUS ===")
        print(f"Run ID: {args.session_id}")
        print(f"Verification: {'PASS' if passed else 'FAIL'}")
        print(f"Diff:\n{diff}")
        print("\nAttention Receipt:")
        print(json.dumps(receipt.model_dump(), indent=2))

        assert receipt.final_verifier_passed is True
        assert receipt.auto_resolved >= 1
        assert receipt.human_interrupts == 1
        print("\n[SUCCESS] Offline demo flow completed successfully!")
        return

    else:
        # Live mode invoking Bedrock
        req = StartRequest(op="start", scenario="concurrency-demo", task=args.task)
        res = service.start(req, session_id=args.session_id)
        print("Result:")
        print(
            json.dumps(
                res.model_dump() if hasattr(res, "model_dump") else res,
                indent=2
            )
        )

        if isinstance(res, NeedsHumanResponse):
            print("\nEncountered human interrupt. Resuming with choice 'A'...")
            resume_req = ResumeRequest(
                op="resume",
                interrupt_id=res.decision.interrupt_id,
                response={
                    "choice_id": "A",
                    "note": "Proceeding with recommendation A in live demo."
                },
            )
            res2 = service.resume(resume_req, session_id=args.session_id)
            print("Final Result:")
            print(
                json.dumps(
                    res2.model_dump() if hasattr(res2, "model_dump") else res2,
                    indent=2
                )
            )


if __name__ == "__main__":
    main()
