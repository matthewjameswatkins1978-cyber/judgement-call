#!/usr/bin/env python3
import argparse
import json
import sys

from bedrock_agentcore import BedrockAgentCoreContext

from judgement_call.runtime import handle_agent_request


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Invoke AgentCore entrypoint locally for start and resume operations."
    )
    parser.add_argument(
        "--op", choices=["start", "resume"], required=True, help="Operation to perform"
    )
    parser.add_argument("--scenario", default="concurrency-demo", help="Scenario name")
    parser.add_argument(
        "--task",
        default="Implement concurrent processing",
        help="Task description for start",
    )
    parser.add_argument("--interrupt-id", help="Interrupt ID for resume")
    parser.add_argument("--choice-id", help="Choice ID for resume response")
    parser.add_argument("--note", help="Optional note for resume response")
    parser.add_argument(
        "--session-id",
        default="local-session-1",
        help="Session ID to pass via BedrockAgentCoreContext",
    )

    args = parser.parse_args()

    # Set context session_id
    BedrockAgentCoreContext.set_request_context(
        request_id="req-local-1", session_id=args.session_id
    )

    payload = {"op": args.op}
    if args.op == "start":
        payload["scenario"] = args.scenario
        payload["task"] = args.task
    elif args.op == "resume":
        if not args.interrupt_id or not args.choice_id:
            print(
                "Error: --interrupt-id and --choice-id are required for resume operation.",
                file=sys.stderr,
            )
            sys.exit(1)
        payload["interrupt_id"] = args.interrupt_id
        payload["response"] = {
            "choice_id": args.choice_id,
            "note": args.note,
        }

    print(f"Invoking AgentCore entrypoint with payload: {json.dumps(payload, indent=2)}")
    print(f"Session ID: {args.session_id}")

    result = handle_agent_request(payload)
    print("\nResult:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
