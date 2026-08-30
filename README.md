# JUDGEMENT CALL

> **"Only ask me when I'm useful."**

---

## 1. Product Overview

**JUDGEMENT CALL** is an enterprise-grade professional coding agent system built on the **Strands Agents SDK** and powered by **Amazon Bedrock** (Claude Sonnet 4.6). It is engineered for professional developers and technical makers who delegate bounded software engineering tasks to autonomous coding agents. 

Unlike traditional agentic frameworks that either run blindly without oversight or inundate developers with a constant stream of low-value interruptions, **JUDGEMENT CALL** introduces an intelligent **Attention Governor** and **Gate Agent** layer. This layer interposes on agent decision proposals (`request_decision()`), evaluating every step against deterministic rules, security policies, and workspace contracts. Safe, low-impact, and reversible internal choices are automatically resolved (`AUTO_RESOLVE`), while genuinely material decisions that require human judgment are escalated as concise **Decision Cards** (`ASK_HUMAN`).

---

## 2. Problem Statement: Human Attention Scarcity with Coding Agents

Modern coding agents generate a high volume of internal decisions during software execution—from choosing internal helper names and loop refactorings to selecting formatting styles and updating type hints. In standard agent setups, every such choice triggers a human interruption or requires configuring brittle auto-approval flags that risk security and behavioral regressions.

This creates a severe bottleneck: **human developer attention scarcity**. Developers are interrupted dozens of times per task with trivial implementation details, leading to alert fatigue, context switching, and abandoned agent delegations. 

**JUDGEMENT CALL** solves this by establishing an automated attention barrier. By filtering out non-material choices and preserving human attention exclusively for irreversible, high-impact, or public-behavior decisions, it maximizes developer leverage and ensures developers are **only asked when their judgment is truly useful**.

---

## 3. Core Concurrency Demo Task

To demonstrate its capabilities, **JUDGEMENT CALL** executes a standardized professional coding task:

> **Task**: Make `process_items()` execute work concurrently while preserving its existing public call signature and successful-result ordering. Do not invent externally visible error semantics if the existing code and tests do not determine them.

During this run, the Worker agent inspects the repository, identifies refactoring choices, proposes parallel execution strategies using standard Python concurrency primitives (`concurrent.futures`), runs tests, and interacts with the Attention Governor.

---

## 4. Two-Role Architecture

The system is built on a clean, two-role separation of concerns:

1. **Worker Agent (`Strands` Coding Agent)**:
   - Responsible for inspecting code (`list_tree`, `read_text`, `search_text`), implementing changes (`write_text`), running tests (`run_tests`), and submitting decision proposals (`request_decision`).
   - Restricted to explicit workspace paths and governed by strict Cedar authorization policies.

2. **Attention Governor & Gate Agent (`Attention Governor / Gate`)**:
   - Interposes on every `request_decision()` call from the Worker.
   - Evaluates proposals using a hybrid model:
     - **Deterministic Rules**: Instantly auto-resolves low-impact, reversible internal refactorings, style updates, and constraint-compliant changes.
     - **Gate Agent Classifier**: Evaluates ambiguous proposals for material risk to public behavior, security, cost, or external side effects.
   - Outputs either `AUTO_RESOLVE` or `ASK_HUMAN` (which triggers a Strands interrupt and renders an interactive Decision Card in the Web UI).

---

## 5. Strands & Bedrock AgentCore Tech Stack

- **Language**: Python 3.12
- **Agent Framework**: Strands Agents SDK (`strands-agents[cedar]`)
- **Foundation Models**: Amazon Bedrock — `eu.anthropic.claude-sonnet-4-6` (Worker & Gate models)
- **Region**: `eu-west-2` (London)
- **Runtime & Orchestration**: Bedrock AgentCore Runtime / AgentCore Starter Toolkit
- **Authorization**: Cedar Policy Engine (`strands-agents[cedar]` / `cedarpy`) with default-deny policies
- **Evaluation**: Strands Agents Evals (`strands-agents-evals`)
- **Web Interface**: FastAPI + Vanilla HTML / CSS / JS
- **Validation & Testing**: Pytest, Ruff static analysis

---

## 6. Local Setup and Run Instructions

### Prerequisites
- Python 3.12+
- AWS Credentials configured for Amazon Bedrock access in `eu-west-2` (or appropriate Bedrock model access).

### Installation

```bash
# Clone repository and navigate to root
cd judgement-call

# Install package in editable mode with development dependencies
python3 -m pip install -e .[dev]
```

### Running the Local Web UI
Start the FastAPI server to use the interactive agent workspace:

```bash
uvicorn judgement_call.web:app --host 127.0.0.1 --port 8000
```
Open `http://localhost:8000` in your browser.

### Running Offline Evaluations
Verify the Attention Governor's evaluation suite (ensuring 0 false suppressions across test cases):

```bash
PYTHONPATH=src python3 evals/run_governor_eval.py
```

### Running Tests
Execute the pytest suite:

```bash
python3 -m pytest
```

---

## 7. Offline Evaluation Metrics (0 False Suppressions)

**JUDGEMENT CALL** includes a rigorous offline evaluation suite (`evals/decision_cases.json` and `evals/run_governor_eval.py`) containing 10 diverse DecisionProposal test cases spanning internal refactoring, public behavior, security, cost, data, and external side effects.

Key evaluated metrics:
- **Total Proposals**: 10
- **Auto-Resolved**: 6 (low-impact, reversible internal and constraint-compliant decisions)
- **Human Interrupts**: 4 (material public-behavior, security, and side-effect decisions)
- **Interruption Reduction**: Reduced developer interruptions from 10 (baseline) down to 4 (governor-enabled)—a **60% reduction in cognitive overhead**.
- **Expected Ask Recall**: `1.0` (100% detection of required human escalations).
- **False Suppression Count**: **`0`** (zero security or behavioral escapes).

---

## 8. Security Model

- **Cedar Authorization**: All tool execution is governed by Cedar policies (`policies/agent.cedar`), enforcing a strict **default-deny** posture. Only 6 authorized product tools are permitted (`list_tree`, `read_text`, `search_text`, `write_text`, `run_tests`, `request_decision`).
- **Path Restrictions**: Workers are strictly bound to designated workspace files (`allowed_paths`) and barred from protected configurations (`protected_paths`).
- **No Arbitrary Shell Execution**: Product workers have no arbitrary shell access, network access, GitHub write access, or package installation capabilities.
- **Credential Isolation**: Zero AWS or sensitive user credentials are exposed to GARY workers or runtime execution environments.

---

## 9. Known Limitations

- **Bounded Scenarios**: Designed specifically for defined coding tasks (such as the concurrency demo task) with pre-configured workspace boundaries.
- **Model Reliance**: Gate classification accuracy relies on Amazon Bedrock Claude Sonnet model responses, supplemented by hardcoded deterministic safety rules.
- **Local Storage**: Session states and ledgers are maintained in local memory / file session managers (`FileSessionManager`) without distributed database persistence.

---

## 10. MIT Licence

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
