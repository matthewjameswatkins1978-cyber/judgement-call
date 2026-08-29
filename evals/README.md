# Attention Governor Evaluation Suite

This directory contains the evaluation dataset, runner script, and comprehensive documentation for assessing the **Attention Governor** in `judgement-call`.

## Overview

The Attention Governor intercepts coding agent decision proposals (`request_decision`) and determines whether a decision can be safely auto-resolved or if it requires human interruption (`ASK_HUMAN`). The goal is to maximize developer productivity and minimize unnecessary cognitive load without compromising safety, public behavior, security, or compliance.

---

## Evaluation Dataset (`evals/decision_cases.json`)

The dataset comprises **10 concrete DecisionProposal test cases** covering all required dimensions and impacts:

1. **Dimensions Covered**:
   - `implementation` (internal code refactoring, helper functions, loop optimization)
   - `public_behavior` (API signature changes, backwards compatibility)
   - `security` (path restrictions, credential handling, secure egress)
   - `cost` (infrastructure scaling expenses)
   - `data` (type hint annotations, persistence safety)
   - `external_side_effect` (network telemetry, external service calls)

2. **Test Case Categories & Breakdown**:
   - **Internal / Reversible Auto-Resolve Cases (4 cases)**: Low impact, reversible implementation decisions (e.g. internal helper renames, code formatting, type hints, internal loop optimizations) that are automatically resolved.
   - **Frozen Constraint Auto-Resolve Cases (2 cases)**: Low impact, reversible decisions complying with workspace frozen constraints like `allowed_paths` and `protected_paths`.
   - **Material Unresolved Ask-Human Cases (4 cases)**: High impact or irreversible decisions spanning public behavior changes, external side effects, security credential handling, and high-cost infrastructure changes that correctly require human intervention.

---

## Evaluation Methodology & Runner (`evals/run_governor_eval.py`)

The evaluation runner script executes the 10 test cases under two distinct modes:

1. **Baseline Mode (`governor_enabled=False`)**:
   - Every `DecisionProposal` forces a human interruption (`ASK_HUMAN`).
   - Represents the traditional agentic workflow where developers must approve every decision.
   - Results in `baseline_human_interrupts == total_proposals` (10 / 10 interrupts).

2. **Attention Governor Mode (`governor_enabled=True`)**:
   - Applies deterministic rules and gate deciders to evaluate proposals.
   - Safe, low-impact, reversible internal and constraint-compliant decisions are auto-resolved.
   - Material risk, high-impact, or irreversible decisions are routed to human review (`ASK_HUMAN`).

---

## Metric Formulas

The evaluation runner computes the following core metrics:

- **`total_proposals`**: Total number of decision proposals evaluated ($N = 10$).
- **`auto_resolved`**: Number of proposals automatically resolved by the governor ($6$).
- **`human_interrupts`**: Number of proposals escalated to human review ($4$).
- **`expected_ask_recall`**: Proportion of required human escalations successfully caught:
  $$\text{expected\_ask\_recall} = \frac{\text{Actual Ask Human Caught}}{\text{Total Expected Ask Human}}$$
- **`false_suppression_count`**: Number of material/risk cases where the governor incorrectly auto-resolved instead of asking human:
  $$\text{false\_suppression\_count} = \sum \mathbb{I}(\text{expected} == \text{ASK\_HUMAN} \land \text{actual} == \text{AUTO\_RESOLVE})$$

**Constraint Enforced**:
$$\text{false\_suppression\_count} == 0$$

---

## Results Summary

Running `python3 evals/run_governor_eval.py` produces:

```json
{
  "total_proposals": 10,
  "auto_resolved": 6,
  "human_interrupts": 4,
  "expected_ask_recall": 1.0,
  "false_suppression_count": 0,
  "baseline_human_interrupts": 10
}
```

- **Interruption Reduction**: Reduced human interruptions from **10** (baseline) down to **4** (governor mode), achieving a **60% reduction in developer interruption overhead**.
- **Safety Guarantee**: **0 false suppressions** (`false_suppression_count == 0`), ensuring 100% safety recall on high-impact, security, public behavior, and cost decisions.
