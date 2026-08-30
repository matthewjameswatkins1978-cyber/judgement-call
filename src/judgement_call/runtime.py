import logging
from typing import Any, Dict

from bedrock_agentcore import BedrockAgentCoreApp, BedrockAgentCoreContext

from judgement_call.contracts import ResumeRequest, RunResponse, StartRequest
from judgement_call.service import JudgementCallService

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
service = JudgementCallService()


@app.entrypoint
def handle_agent_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    AgentCore runtime entrypoint wrapping JudgementCallService.
    Accepts start/resume payloads and maps context.session_id.
    """
    session_id = BedrockAgentCoreContext.get_session_id()

    op = payload.get("op")
    if not op:
        # Fallback or infer operation based on keys
        if "interrupt_id" in payload or "response" in payload:
            op = "resume"
        else:
            op = "start"
        payload["op"] = op

    try:
        if op == "start":
            start_req = StartRequest(**payload)
            response: RunResponse = service.start(start_req, session_id=session_id)
        elif op == "resume":
            resume_req = ResumeRequest(**payload)
            response = service.resume(resume_req, session_id=session_id)
        else:
            raise ValueError(f"Unknown operation: {op}")

        return response.model_dump()
    except Exception as e:
        logger.exception(f"Error handling AgentCore request: {e}")
        return {
            "status": "failed",
            "run_id": session_id or payload.get("run_id", "unknown"),
            "code": "INTERNAL_ERROR",
            "message": str(e),
            "receipt": {
                "decision_proposals": 0,
                "auto_resolved": 0,
                "human_interrupts": 0,
                "policy_denials": 0,
                "tool_calls": 0,
                "test_runs": 0,
                "final_verifier_passed": False,
            },
        }


if __name__ == "__main__":
    app.run()
