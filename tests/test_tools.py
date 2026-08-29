from judgement_call.contracts import TaskContract
from judgement_call.ledger import RunLedger
from judgement_call.tools import ProductToolContext, create_product_tools
from judgement_call.verifier import IndependentVerifier
from judgement_call.workspace import WorkspaceManager


def test_product_tools_execution(tmp_path):
    fix_dir = tmp_path / "fixture"
    fix_dir.mkdir()
    (fix_dir / "test.txt").write_text("apple banana cherry")

    wm = WorkspaceManager(fixture_src=str(fix_dir))
    ledger = RunLedger()
    ctx = ProductToolContext(
        workspace=wm,
        ledger=ledger,
        allowed_paths=["test.txt"],
        acceptance_command="python -c 'print(\"ok\", flush=True)'",
    )
    tools = create_product_tools(ctx)
    tool_map = {t.__name__: t for t in tools}

    try:
        # test list_tree
        tree_res = tool_map["list_tree"](".")
        assert "test.txt" in tree_res

        # test read_text
        read_res = tool_map["read_text"]("test.txt")
        assert read_res == "apple banana cherry"

        # test search_text
        search_res = tool_map["search_text"]("banana")
        assert "banana" in search_res

        # test write_text (allowed)
        write_res = tool_map["write_text"]("test.txt", "updated content")
        assert "Successfully wrote" in write_res
        assert tool_map["read_text"]("test.txt") == "updated content"

        # test write_text (forbidden / policy denied)
        forbidden_res = tool_map["write_text"]("forbidden.txt", "evil")
        assert "Policy denied write" in forbidden_res
        assert ledger.receipt().policy_denials == 1

        # test run_tests
        test_res = tool_map["run_tests"]()
        assert "ok" in test_res
        assert ledger.receipt().test_runs == 1

        # test request_decision
        dec_res = tool_map["request_decision"](
            question="Choice?",
            options=[{"id": "A", "label": "A", "consequence": "A"}],
            recommendation="A",
            dimensions=["implementation"],
            impact="low",
            reversible=True,
            evidence="Ev",
        )
        assert dec_res == "A"
    finally:
        wm.cleanup()


def test_verifier_gating():
    wm = WorkspaceManager(fixture_src="fixtures/concurrency_demo")
    contract = TaskContract(
        scenario="concurrency-demo",
        allowed_paths=["src/demoqueue/processor.py"],
        protected_paths=["pyproject.toml"],
        acceptance_command="python -m pytest -q",
        frozen_constraints={
            "public_signature": "process_items(items, worker)",
            "success_result_order": "input-order",
            "dependency_policy": "no-new-runtime-dependencies",
            "interface_style": "synchronous",
        },
    )

    verifier = IndependentVerifier(workspace=wm, contract=contract)
    try:
        passed, msg = verifier.verify()
        assert passed is True, f"Verifier failed unexpectedly: {msg}"
    finally:
        wm.cleanup()


def test_verifier_catches_unallowed_edit():
    wm = WorkspaceManager(fixture_src="fixtures/concurrency_demo")
    contract = TaskContract(
        scenario="concurrency-demo",
        allowed_paths=["src/demoqueue/processor.py"],
        protected_paths=["pyproject.toml"],
        acceptance_command="python -m pytest -q",
        frozen_constraints={
            "public_signature": "process_items(items, worker)",
            "success_result_order": "input-order",
            "dependency_policy": "no-new-runtime-dependencies",
            "interface_style": "synchronous",
        },
    )

    # Edit pyproject.toml which is not in allowed_paths
    (wm.root / "pyproject.toml").write_text("corrupted")

    verifier = IndependentVerifier(workspace=wm, contract=contract)
    try:
        passed, msg = verifier.verify()
        assert passed is False
        assert "not in allowed_paths" in msg
    finally:
        wm.cleanup()
