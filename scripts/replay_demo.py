#!/usr/bin/env python3
import json
import time


def main() -> None:
    print("==================================================")
    print("                  [REPLAY MODE]                   ")
    print("==================================================")
    print("Replaying stored timeline events (tool calls, auto-resolutions,")
    print("Decision Card presentation, resume, verified receipt)...\n")

    events = [
        {
            "step": 1,
            "event": "tool_call",
            "details": "Worker executed list_tree on workspace 'fixtures/concurrency_demo'."
        },
        {
            "step": 2,
            "event": "decision_proposal",
            "details": "Proposal: Use ThreadPoolExecutor or "
                       "ProcessPoolExecutor? (Reversible, low impact)."
        },
        {
            "step": 3,
            "event": "auto_resolution",
            "details": "Attention Governor auto-resolved decision to 'A' "
                       "(ThreadPoolExecutor) [auto_resolved: 1]."
        },
        {
            "step": 4,
            "event": "tool_call",
            "details": "Worker executed write_text on 'src/demoqueue/processor.py' "
                       "using concurrent.futures with input order preserved."
        },
        {
            "step": 5,
            "event": "decision_proposal",
            "details": "Proposal: Error handling strategy for worker "
                       "exceptions during concurrent batch execution? (Material choice)."
        },
        {
            "step": 6,
            "event": "human_interrupt",
            "details": "Attention Governor presented Decision Card "
                       "int-replay-1 requiring human intervention [human_interrupts: 1]."
        }
    ]

    for ev in events:
        print(f"[Step {ev['step']}] [{ev['event'].upper()}] {ev['details']}")
        time.sleep(0.2)

    print("\n--- DECISION CARD PRESENTED ---")
    decision_card = {
        "interrupt_id": "int-replay-1",
        "question": "Error handling strategy for worker "
                    "exceptions during concurrent batch execution?",
        "why_human": "High impact architectural choice on error semantics.",
        "options": [
            {
                "id": "A",
                "label": "Propagate exceptions immediately (fail fast)",
                "consequence": "Fails test on first error"
            },
            {
                "id": "B",
                "label": "Swallow and return None",
                "consequence": "Silently ignores errors"
            }
        ],
        "recommendation": "A",
        "evidence": "Material architectural tradeoff requiring human review."
    }
    print(json.dumps(decision_card, indent=2))

    print(
        "\n[Step 7] [RESUME] Human responded with choice 'A' "
        "(Note: 'Proceeding with fail-fast exception propagation.')."
    )
    time.sleep(0.3)

    print(
        "[Step 8] [VERIFICATION] IndependentVerifier executed "
        "acceptance tests ('python -m pytest -q'). Result: PASS."
    )

    receipt = {
        "decision_proposals": 2,
        "auto_resolved": 1,
        "human_interrupts": 1,
        "policy_denials": 0,
        "tool_calls": 5,
        "test_runs": 1,
        "final_verifier_passed": True
    }

    print("\n=== REPLAY COMPLETED ===")
    print("Final Attention Receipt:")
    print(json.dumps(receipt, indent=2))
    print(
        "\n[REPLAY MODE] Replay finished successfully "
        "without masquerading as live AI."
    )


if __name__ == "__main__":
    main()
