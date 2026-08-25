# JUDGEMENT CALL — Build Specification

**Attention Governor** — Only ask me when I'm useful.

## Hackathon

AWS / Amazon Agents for Humans Hackathon
Track: Professional Agents
Deadline: 15 September 2026 1:00am BST

## Core Goal

Build a Strands-based professional coding agent that completes a bounded
software task autonomously while suppressing unnecessary human interruptions
and pausing only when human judgement would materially change the outcome.

## User

Software developers and technical makers delegating work to coding agents.

## Core Demo Task

Make process_items() execute work concurrently while preserving its existing
public call signature and successful-result ordering. Do not invent externally
visible error semantics if the existing code and tests do not determine them.

## Demo Must Show

1. Worker inspects repository.
2. Worker identifies choices.
3. Low-value choices are automatically resolved by Governor.
4. Worker edits code.
5. Worker tests.
6. One genuinely unresolved public-behaviour decision appears.
7. Human receives one concise Decision Card.
8. Human answers.
9. Same run resumes.
10. Independent verifier passes.
11. Final diff + Attention Receipt shown.

The concurrency patch itself is not the product.
The product is the boundary between machine work and scarce human judgement.

## Architecture

Two AI roles:

1. **Worker Agent** — Strands coding agent
2. **Attention Governor / Gate** — Custom Strands intervention on request_decision()

```
Developer
   |
   v
Local FastAPI UI / AgentCore invocation
   |
   v
JudgementCallService
   |
   v
Strands Worker Agent
   |
   +---- normal tool ----------------------+
   |                                      |
   |                                      v
   |                              Cedar Authorization
   |                                      |
   |                                      v
   |                                  workspace
   |
   +---- request_decision() --------------+
                                          |
                                          v
                                 Attention Governor
                                   /           \
                             deterministic    ambiguous
                                 |                |
                                 v                v
                           AUTO_RESOLVE       Gate Agent
                                                 |
                                      AUTO_RESOLVE / ASK
                                                 |
                                             if ASK
                                                 |
                                                 v
                                          Strands interrupt
                                                 |
                                                 v
                                           Decision Card
                                                 |
                                          human response
                                                 |
                                                 v
                                               resume
```

## Tech Stack

- Language: Python 3.12
- Framework: Strands Agents SDK
- Package manager: pip
- Web: FastAPI + vanilla HTML/CSS/JS
- Schemas: Pydantic 2
- Database: none
- Queue: none
- Worker model: eu.anthropic.claude-sonnet-4-6
- Gate model: eu.anthropic.claude-sonnet-4-6
- Provider: Amazon Bedrock
- Authorization: strands-agents[cedar]
- Evaluation: strands-agents-evals
- AgentCore: bedrock-agentcore
- Deployment: bedrock-agentcore-starter-toolkit / agentcore CLI
- Cloud: Amazon Bedrock, AgentCore Runtime, eu-west-2
- Tests: pytest
- Static check: Ruff
- Build: python build
- Licence: MIT

## Repository Shape

```
/
├── LICENSE
├── README.md
├── pyproject.toml
├── .gitignore
├── src/judgement_call/
│   ├── __init__.py
│   ├── contracts.py
│   ├── ledger.py
│   ├── workspace.py
│   ├── tools.py
│   ├── verifier.py
│   ├── gate.py
│   ├── governor.py
│   ├── agent.py
│   ├── service.py
│   ├── runtime.py
│   └── web.py
├── static/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── fixtures/concurrency_demo/
│   ├── pyproject.toml
│   ├── src/demoqueue/
│   │   ├── __init__.py
│   │   └── processor.py
│   └── tests/
│       └── test_processor.py
├── policies/
│   └── agent.cedar
├── evals/
│   ├── decision_cases.json
│   ├── run_governor_eval.py
│   └── README.md
├── scripts/
│   ├── demo_local.py
│   ├── invoke_agentcore.py
│   └── replay_demo.py
├── deploy/
│   └── README.md
├── docs/
│   ├── build-spec.md
│   ├── architecture.md
│   ├── architecture.mmd
│   └── demo.md
└── tests/
    ├── test_scaffold.py
    ├── test_contracts.py
    ├── test_workspace.py
    ├── test_tools.py
    ├── test_governor.py
    ├── test_service.py
    ├── test_runtime.py
    ├── test_web.py
    ├── test_evals.py
    └── live/
        └── test_demo_flow.py
```

## Frozen Contracts

### Service

```python
class JudgementCallService:
    def start(self, request: StartRequest, session_id: str) -> RunResponse: ...
    def resume(self, request: ResumeRequest, session_id: str) -> RunResponse: ...
```

### Start Request

```json
{
  "op": "start",
  "scenario": "concurrency-demo",
  "task": "Make process_items() execute work concurrently..."
}
```

### Resume Request

```json
{
  "op": "resume",
  "interrupt_id": "abc123",
  "response": {"choice_id": "A", "note": ""}
}
```

### Task Contract

```json
{
  "scenario": "concurrency-demo",
  "allowed_paths": ["src/demoqueue/processor.py", "tests/test_processor.py"],
  "protected_paths": ["pyproject.toml"],
  "acceptance_command": "python -m pytest -q",
  "frozen_constraints": {
    "public_signature": "process_items(items, worker)",
    "success_result_order": "input-order",
    "dependency_policy": "no-new-runtime-dependencies",
    "interface_style": "synchronous"
  }
}
```

### Decision Proposal

Fields: question, options (2-4, each with id/label/consequence),
recommendation, dimensions, impact, reversible, constraint_key, evidence.

### Gate Decision

```json
{"action": "AUTO_RESOLVE", "choice_id": "A", "reason": "..."}
```
or
```json
{"action": "ASK_HUMAN", "choice_id": null, "reason": "..."}
```

### Decision Card

Fields: interrupt_id, question, why_human, options, recommendation, evidence.

### Attention Receipt

```json
{
  "decision_proposals": 3,
  "auto_resolved": 2,
  "human_interrupts": 1,
  "policy_denials": 0,
  "tool_calls": 18,
  "test_runs": 2,
  "final_verifier_passed": true
}
```

## Worker Authority

Product Worker tools: list_tree, read_text, search_text, write_text,
run_tests, request_decision. No shell, no network, no GitHub, no package install.

## Attention Governor Rules

Deterministic rules first. If ambiguous, Gate Agent classifies.
Gate outcomes: AUTO_RESOLVE or ASK_HUMAN.

## Limits

Max 40 product tool calls per run. Max 8 DecisionProposals.

## Frozen Decisions

1. JUDGEMENT CALL name
2. Attention Governor concept
3. Professional Agents track
4. Python 3.12
5. Strands Agents SDK
6. Amazon Bedrock
7. Claude Sonnet 4.6
8. eu-west-2
9. AgentCore Runtime
10. /mnt/workspace session storage
11. FileSessionManager
12. Cedar default deny
13. raw Strands interrupts
14. one Worker Agent
15. one no-tools Gate Agent
16. no swarm/graph
17. no arbitrary shell product tool
18. fixed Python fixture
19. user cannot provide test commands
20. deterministic final verifier
21. no database/queue/Redis
22. FastAPI + vanilla HTML/CSS/JS
23. no GitHub write access in product
24. no AWS credentials to GARY workers
25. baseline asks on every valid DecisionProposal
26. measure suppressed proposals, not time savings
27. no GARY/Resolve/Warren source reuse
28. frozen public schemas above
