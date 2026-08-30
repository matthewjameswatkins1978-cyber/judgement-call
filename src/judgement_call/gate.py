import json
import re
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
            decision = self._parse_agent_response(str(resp), proposal)
            if decision is not None:
                return decision
            return GateDecision(
                action="ASK_HUMAN",
                choice_id=None,
                reason="Gate agent response was invalid; failing closed to human review.",
            )

        # The no-tool Gate Agent is the only fallback for unresolved proposals.
        # Keep its local heuristic conservative: only an internal, reversible,
        # low-impact proposal may be auto-resolved without model classification.
        safe_dimensions = {"implementation"}
        if (
            proposal.impact == "low"
            and proposal.reversible
            and set(proposal.dimensions).issubset(safe_dimensions)
        ):
            return GateDecision(
                action="AUTO_RESOLVE",
                choice_id=proposal.recommendation,
                reason="Low impact and reversible internal decision auto-resolved.",
            )
        return GateDecision(
            action="ASK_HUMAN",
            choice_id=None,
            reason="Unresolved material decision requires human attention.",
        )

    @staticmethod
    def _parse_agent_response(
        text: str, proposal: DecisionProposal
    ) -> GateDecision | None:
        """Parse only the frozen two-action Gate contract, failing closed."""
        candidates = [text.strip()]
        candidates.extend(re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL))
        option_ids = {option.id for option in proposal.options}

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if not isinstance(payload, dict):
                continue
            action = payload.get("action")
            reason = str(payload.get("reason") or "Gate agent classified the proposal.")
            if action == "AUTO_RESOLVE":
                choice_id = payload.get("choice_id") or proposal.recommendation
                if choice_id not in option_ids:
                    return None
                return GateDecision(
                    action="AUTO_RESOLVE",
                    choice_id=choice_id,
                    reason=reason,
                )
            if action == "ASK_HUMAN":
                return GateDecision(
                    action="ASK_HUMAN",
                    choice_id=None,
                    reason=reason,
                )
        return None
