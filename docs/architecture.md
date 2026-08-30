# JUDGEMENT CALL — Architecture Documentation

This document details the internal architecture, component interactions, deterministic attention governor rules, Cedar authorization model, and state lifecycle of **JUDGEMENT CALL**.

---

## 1. System Overview & Component Interaction

**JUDGEMENT CALL** operates through a tightly coupled yet modular pipeline designed to balance autonomous agent execution with intelligent human oversight:

```
Developer / Web UI
       │
       ▼
 FastAPI Service (`JudgementCallService`)
       │
       ▼
Strands Runtime & Session Manager (`FileSessionManager`)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
Worker Agent (`Strands` Agent)    Cedar Policy Engine (`policies/agent.cedar`)
       │                                 │
       ├─► Product Tools (list, read,    │ (Default Deny: validates
       │   search, write, test)          │  principal & action)
       │                                 │
       └─► `request_decision()` ─────────┘
                 │
                 ▼
       Attention Governor (`governor.py`)
                 │
        ┌────────┴────────┐
        ▼                 ▼
  Deterministic      Gate Classifier Agent
     Rules               (`gate.py`)
        │                 │
        └────────┬────────┘
                 │
          ┌──────┴──────┐
          ▼             ▼
    AUTO_RESOLVE    ASK_HUMAN
                    │
                    ▼
            Strands Interrupt
                    │
                    ▼
              Decision Card (Web UI)
                    │
                    ▼
             Resume Execution
```

### Component Breakdown
- **FastAPI Web App (`web.py`)**: Exposes REST endpoints (`/api/start`, `/api/resume`, `/api/session/{id}`) and serves static assets (`index.html`, `app.js`, `style.css`).
- **Service Layer (`service.py`)**: Manages session lifecycles, orchestrates Start and Resume requests, tracks decision ledgers, and interfaces with the Strands runtime.
- **Worker Agent (`agent.py`)**: Executes the core coding task using permitted tools while constrained by workspace rules.
- **Tools (`tools.py`)**: Encapsulates workspace interactions (`list_tree`, `read_text`, `search_text`, `write_text`, `run_tests`) and decision requests (`request_decision`).
- **Workspace Manager (`workspace.py`)**: Enforces file-level path validation (`allowed_paths`, `protected_paths`).
- **Attention Governor (`governor.py`)**: Interposes on `request_decision` tool calls to filter out non-material choices.
- **Gate Agent (`gate.py`)**: A lightweight, zero-tool LLM classifier that evaluates ambiguous decision proposals.
- **Verifier (`verifier.py`)**: Executes deterministic test assertions and acceptance commands against the workspace.

---

## 2. Deterministic Governor Rules

The Attention Governor evaluates incoming `DecisionProposal` payloads using a multi-tiered evaluation strategy:

1. **Deterministic Auto-Resolve Rules**:
   - **Internal / Reversible**: Proposals where `reversible=true`, impact is `low` or `medium`, and the only dimension is `implementation` are automatically resolved (`AUTO_RESOLVE`). The Governor returns `Guide` feedback containing the selected choice so the Worker continues without repeating the proposal.
   - **Constraint Compliance**: A proposal whose declared `constraint_key` matches a non-empty frozen task constraint is auto-resolved when the constraint determines the recommended option and the proposal remains reversible and low/medium impact. The Governor also returns `Guide` feedback for this path.

2. **Ambiguity Escalation (Gate Classifier)**:
   - If a proposal involves high impact, irreversible changes, public behavior modifications (API signature changes, backwards compatibility breaks), security concerns (path validation, credentials), cost impacts, or external side effects, deterministic rules pass it to the **Gate Agent**.
   - The Gate Agent classifies the proposal as either:
     - `AUTO_RESOLVE` (if deemed low material risk upon closer analysis), or
     - `ASK_HUMAN` (escalating to human review).

3. **Baseline Guarantee**:
   - When governor evaluation is disabled (e.g. in baseline comparison mode), every valid proposal forces `ASK_HUMAN`.

---

## 3. Cedar Authorization Model

Security is enforced via **Cedar Policy** integration (`strands-agents[cedar]` / `policies/agent.cedar`), operating under a strict **default-deny** posture.

### Policy Definition (`policies/agent.cedar`)
```cedar
// Cedar default deny policy permitting exact 6 product tools:
// list_tree, read_text, search_text, write_text, run_tests, request_decision

permit(
    principal,
    action in [
        Action::"list_tree",
        Action::"read_text",
        Action::"search_text",
        Action::"write_text",
        Action::"run_tests",
        Action::"request_decision"
    ],
    resource
);
```

### Authorization Flow
- When the Worker agent attempts to invoke any tool, the Strands framework queries the Cedar policy engine.
- Only the 6 explicitly declared product actions are permitted. Any attempt to invoke unlisted actions (such as arbitrary shell commands, network requests, or file deletions outside scope) is denied instantly by the policy engine.

---

## 4. State Lifecycle

The execution lifecycle of a session flows through distinct phases tracked in memory and ledgers:

1. **Initialization (`start`)**:
   - Client sends a Start Request (`scenario`, `task`).
   - `JudgementCallService` initializes a session ID, sets up workspace file boundaries, and starts the Strands agent execution loop.

2. **Execution & Interposition**:
   - Worker explores workspace, reads files, and performs edits.
   - When a design choice arises, Worker invokes `request_decision()`.
   - Attention Governor intercepts the call.

3. **Governor Evaluation**:
   - **Auto-Resolve Path**: The Gate contract records `AUTO_RESOLVE`; the Governor returns a `Guide` action containing the selected choice. The Worker continues without an interruption. Ledger records the resolved choice.
   - **Ask-Human Path**: The Gate contract records `ASK_HUMAN`; the Governor calls the raw Strands `event.interrupt()` path. The first call pauses the loop and creates a **Decision Card**. On resume, the interrupt returns the selected choice and the Governor returns `Proceed` so the original tool call can continue.

4. **Human Response & Resumption (`resume`)**:
   - Developer reviews the Decision Card in the Web UI and selects a choice.
   - Client sends Resume Request (`interrupt_id`, `response`).
   - Service injects the human response back into the Strands agent runtime session.
   - Worker resumes execution.

5. **Verification & Completion**:
   - Worker runs acceptance tests via `run_tests`.
   - Verifier validates final test success and generates an **Attention Receipt** detailing total proposals, auto-resolved count, human interrupts, and verification status.
