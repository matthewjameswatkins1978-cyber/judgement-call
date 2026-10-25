# Judgement Call

> **Only ask me when I'm useful.**

Coding agents should be able to make routine, reversible implementation choices without requesting permission for every variable name. They should **not** quietly decide that a public API change, security exception or external effect is routine.

**Judgement Call** explores that distinction. It's a Python/Strands coding-agent prototype with an **Attention Governor** that classifies proposed decisions, resolves low-impact choices automatically and returns consequential questions to a human as focused Decision Cards.

**Status:** bounded hackathon/prototype system, version 0.1.0. It is not a production-certified agent service.

## The idea

A worker can propose a change. Before interrupting the person who delegated the task, the Governor asks whether human judgement is actually necessary.

```text
Worker proposes a decision
           |
           v
Deterministic guardrails + Gate classification
           |
           +---- AUTO_RESOLVE  →  routine bounded choice
           |
           +---- ASK_HUMAN    →  interrupt with a Decision Card
```

**Attention is not permission.** Reducing interruptions does not give an agent more authority. Workspace and tool permissions must still be enforced by separate, deterministic controls.

## A concrete test

The included demonstration asks a worker to make `process_items()` run concurrently **without** changing its public signature or the order of successful results.

That should raise very different types of questions. Picking a private helper name is probably routine. Inventing new externally observable error semantics is not.

The worker has a constrained set of operations: inspect files, read/search text, write permitted text, run tests and request a decision. It does not receive unrestricted shell execution.

## Try it locally

You need Python **3.12+** and AWS credentials with suitable access to the configured Amazon Bedrock models to run the live agent path. Local tests and the offline decision fixtures do not require launching a Bedrock worker.

```sh
git clone https://github.com/matthewjameswatkins1978-cyber/judgement-call.git
cd judgement-call
python -m pip install -e ".[dev]"
python -m pytest
python evals/run_governor_eval.py
```

For the local web interface:

```sh
uvicorn judgement_call.web:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The web app provides the start/resume interaction around the bounded worker.

## What the fixture evaluation says

The repository includes **10 curated decision proposals** in `evals/decision_cases.json`. Its documented expected split is six automatically resolved decisions and four escalations, equivalent to 60% fewer interruptions **on that small fixture set**.

This is a useful design check, **not** evidence of a 60% reduction on real developer workloads or proof that a model never misses a dangerous decision. Evaluation quality depends on the cases you test and the model/guardrail behaviour you actually measure.

Run the offline evaluator yourself to see the current results.

## Architecture and boundaries

| Layer | Responsibility |
| --- | --- |
| Strands worker | Inspect, edit and verify a bounded coding task |
| Attention Governor | Route a decision proposal without flooding the human |
| Gate classifier | Assess ambiguous materiality and risk |
| Cedar policies | Enforce permitted tool use and workspace restrictions |
| FastAPI interface | Present the human interruption and resume path |

The prototype uses Amazon Bedrock, Strands Agents SDK, Cedar integration, FastAPI and Python tests. The documented deployment path uses AWS Bedrock AgentCore, but running the local server is not the same as operating a hardened multi-user service.

Known limitations include a narrow coding-task scope, model-dependent classification, local session state and the absence of production-scale security/operational assurance.

## Licence

MIT. See [LICENSE](LICENSE).
