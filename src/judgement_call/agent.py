import logging
from typing import Any, Callable

from strands import Agent
from strands.vended_interventions.cedar import CedarAuthorization

from judgement_call.contracts import TaskContract
from judgement_call.governor import AttentionGovernor
from judgement_call.ledger import RunLedger
from judgement_call.tools import ProductToolContext, create_product_tools
from judgement_call.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


def create_worker_agent(
    workspace: WorkspaceManager,
    ledger: RunLedger,
    contract: TaskContract,
    governor: AttentionGovernor,
    model_id: str = "eu.anthropic.claude-sonnet-4-6",
) -> Agent:
    ctx = ProductToolContext(
        workspace=workspace,
        ledger=ledger,
        allowed_paths=contract.allowed_paths,
        acceptance_command=contract.acceptance_command,
    )
    tools = create_product_tools(ctx)

    # Setup Cedar authorization policy if policy file exists
    intervention_handlers = [governor]
    try:
        from pathlib import Path
        policy_path = Path("policies/agent.cedar")
        if policy_path.exists():
            cedar_auth = CedarAuthorization(policy_file=str(policy_path))
            intervention_handlers.append(cedar_auth)
    except Exception as e:
        logger.warning(f"Could not load Cedar authorization policy: {e}")

    system_prompt = (
        f"You are a professional coding agent working on the {contract.scenario} scenario.\n"
        f"Task: {contract.allowed_paths}\n"
        f"Frozen Constraints:\n"
    )
    for k, v in contract.frozen_constraints.items():
        system_prompt += f"- {k}: {v}\n"
    system_prompt += (
        "Inspect the codebase using list_tree, read_text, search_text, make code changes using write_text, "
        "run acceptance tests using run_tests, and request decisions using request_decision when trade-offs arise.\n"
        "Always provide concrete evidence when requesting decisions."
    )

    agent = Agent(
        model=model_id,
        system_prompt=system_prompt,
        tools=tools,
        interventions=intervention_handlers,
    )
    return agent
