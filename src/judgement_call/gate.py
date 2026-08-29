from typing import Protocol, runtime_checkable

from judgement_call.contracts import DecisionProposal, GateDecision


@runtime_checkable
class GateDecider(Protocol):
    def decide(self, proposal: DecisionProposal) -> GateDecision:
        ...


class StrandsGateDecider:
    def __init__(self, agent=None, client=None) -> None:
        self.agent = agent
        self.client = client

    def decide(self, proposal: DecisionProposal) -> GateDecision:
        if self.agent is not None:
            # Use Strands gate agent or model call
            prompt = (
                f"Evaluate this decision proposal:\n"
                f"Question: {proposal.question}\n"
                f"Options: {[opt.model_dump() for opt in proposal.options]}\n"
                f"Recommendation: {proposal.recommendation}\n"
                f"Dimensions: {proposal.dimensions}\n"
                f"Impact: {proposal.impact}\n"
                f"Reversible: {proposal.reversible}\n"
                f"Evidence: {proposal.evidence}\n"
                f"Return a JSON object with action (AUTO_RESOLVE or ASK_HUMAN), "
                f"choice_id (if AUTO_RESOLVE), and reason."
            )
            resp = self.agent(prompt)
            # parse response or handle
            # For robustness, if agent is a callable or Agent instance
            text = str(resp)
            if "AUTO_RESOLVE" in text:
                return GateDecision(
                    action="AUTO_RESOLVE",
                    choice_id=proposal.recommendation,
                    reason="Gate agent auto-resolved based on recommendation.",
                )
            else:
                return GateDecision(
                    action="ASK_HUMAN",
                    choice_id=None,
                    reason="Gate agent classified as ambiguous, requesting human judgment.",
                )

        # Fallback heuristic if no agent/client provided
        if proposal.impact == "low" and proposal.reversible:
            return GateDecision(
                action="AUTO_RESOLVE",
                choice_id=proposal.recommendation,
                reason="Low impact and reversible decision auto-resolved.",
            )
        return GateDecision(
            action="ASK_HUMAN",
            choice_id=None,
            reason="Medium/high impact or irreversible decision requires human attention.",
        )
