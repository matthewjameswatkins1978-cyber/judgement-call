import json
from pathlib import Path

from evals.run_governor_eval import run_evaluation
from judgement_call.contracts import DecisionProposal


def test_decision_cases_load_cleanly():
    dataset_path = Path("evals/decision_cases.json")
    assert dataset_path.exists(), "evals/decision_cases.json must exist"

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    assert isinstance(cases, list)
    assert len(cases) >= 10, "Dataset must contain at least 10 test cases"

    auto_internal = 0
    auto_constraint = 0
    ask_human = 0
    dimensions_seen = set()

    for item in cases:
        assert "id" in item
        assert "expected_action" in item
        assert "proposal" in item

        category = item.get("category")
        if category == "auto_resolve_internal":
            auto_internal += 1
        elif category == "auto_resolve_constraint":
            auto_constraint += 1
        elif category == "ask_human_material":
            ask_human += 1

        proposal_data = item["proposal"]
        proposal = DecisionProposal(**proposal_data)
        assert proposal.question
        assert 2 <= len(proposal.options) <= 4
        for dim in proposal.dimensions:
            dimensions_seen.add(dim)

    assert auto_internal >= 4, (
        f"Expected at least 4 internal auto-resolve cases, found {auto_internal}"
    )
    assert auto_constraint >= 2, (
        "Expected at least 2 frozen-constraint auto-resolve cases, "
        f"found {auto_constraint}"
    )
    assert ask_human >= 4, (
        f"Expected at least 4 material ask-human cases, found {ask_human}"
    )

    required_dims = {
        "implementation",
        "public_behavior",
        "security",
        "cost",
        "data",
        "external_side_effect",
    }
    for dim in required_dims:
        assert dim in dimensions_seen, (
            f"Required dimension '{dim}' not found in test dataset"
        )


def test_run_governor_eval_metrics():
    metrics = run_evaluation()

    assert metrics["total_proposals"] == 10
    assert metrics["auto_resolved"] == 6
    assert metrics["human_interrupts"] == 4
    assert metrics["expected_ask_recall"] == 1.0
    assert metrics["false_suppression_count"] == 0
    assert metrics["baseline_human_interrupts"] == 10


def test_false_suppression_count_zero_without_aws_credentials():
    metrics = run_evaluation()
    assert metrics["false_suppression_count"] == 0, (
        "false_suppression_count must be exactly 0"
    )
