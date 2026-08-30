# Bedrock AgentCore Runtime Deployment Guide (eu-west-2)

This document describes how to deploy the **Judgement Call** agent as a Bedrock AgentCore Runtime service in `eu-west-2` with persistent `/mnt/workspace` session storage.

## Architecture Overview

- **Runtime Framework:** `bedrock-agentcore` (`BedrockAgentCoreApp`)
- **Region:** `eu-west-2` (London)
- **Session Storage:** `/mnt/workspace` mounted volume for persistent workspace state across agent runs and interactive pauses/resumes.
- **Entrypoint:** `src/judgement_call/runtime.py:handle_agent_request`

## Prerequisites

1. AWS CLI configured with permissions for Amazon Bedrock and AgentCore in `eu-west-2`.
2. Python 3.12+ and Poetry / pip.
3. `bedrock-agentcore-starter-toolkit` installed (`pip install .[deploy]`).

## Deployment Steps

### 1. Build and Configure

Ensure dependencies and packaging configurations in `pyproject.toml` are up to date:

```bash
pip install -e .[deploy,dev]
```

### 2. Configure AgentCore Deployment

Create or update your AgentCore deployment configuration (e.g., `agentcore.yaml` or via toolkit):

```yaml
app_name: judgement-call
region: eu-west-2
entrypoint: src/judgement_call.runtime:app
storage:
  mount_point: /mnt/workspace
  size_gb: 10
```

### 3. Deploy to eu-west-2

Use the AgentCore starter toolkit or AWS CLI to package and deploy to `eu-west-2`:

```bash
agentcore deploy --region eu-west-2 --mount /mnt/workspace
```

### 4. Verifying Local and Remote Invocation

You can invoke the runtime entrypoint locally using the provided CLI utility:

```bash
python scripts/invoke_agentcore.py --op start --scenario concurrency-demo --task "Make process_items asynchronous" --session-id session-101
```

For resuming after an interrupt:

```bash
python scripts/invoke_agentcore.py --op resume --interrupt-id int-123 --choice-id A --note "Proceeding with async" --session-id session-101
```
