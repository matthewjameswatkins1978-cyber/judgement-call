import logging
from collections.abc import Mapping
from typing import Any

from strands.interrupt import InterruptException
from strands.interventions import InterventionHandler
from strands.interventions.actions import Guide, Proceed

from judgement_call.contracts import (
    DecisionCard,
    DecisionProposal,
    GateDecision,
)
from judgement_call.gate import GateDecider, StrandsGateDecider
from judgement_call.ledger import RunLedger

logger = logging.getLogger(__name__)


class AttentionGovernor(InterventionHandler):
    name = "attention-governor"

    def __init__(
        self,
        ledger: RunLedger,
        gate_decider: GateDecider | None = None,
        governor_enabled: bool = True,
        frozen_constraints: Mapping[str, str] | None = None,
        on_error: str = "throw",
    ) -> None:
        self.ledger = ledger
        self.gate_decider = gate_decider or StrandsGateDecider()
        self.governor_enabled = governor_enabled
        self.frozen_constraints = dict(frozen_constraints or {})
        self._on_error = on_error
        self.pending_interrupts: dict[str, DecisionCard] = {}

    @property
    def on_error(self) -> str:
        return self._on_error

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        tool_name = getattr(event, "tool_name", None) or getattr(event, "name", None)
        tool_use = getattr(event, "tool_use", None)
        if not tool_name and isinstance(tool_use, dict):
            tool_name = tool_use.get("name")

        tool_args = getattr(event, "tool_args", None)
        if tool_args is None:
            tool_args = getattr(event, "arguments", None)
        if tool_args is None and isinstance(tool_use, dict):
            tool_args = tool_use.get("input", {})
        if not isinstance(tool_args, dict):
            tool_args = {}

        self.ledger.record_tool_call()

        if tool_name == "request_decision":
            self.ledger.record_decision_proposal()

            # Validate before applying baseline or Governor policy. Baseline mode
            # asks on every valid proposal; malformed proposals still need guidance.
            try:
                proposal = self._proposal_from_tool_args(tool_args)
            except ValueError as exc:
                return Guide(
                    feedback=f"Invalid DecisionProposal structure: {exc}",
                    reason="Validation failed.",
                )

            # Evidence and option quality are worker-repair concerns, not human
            # decisions. Guide the worker to produce a complete proposal.
            if not proposal.evidence.strip():
                return Guide(
                    feedback=(
                        "DecisionProposal missing required evidence. "
                        "Investigate the repository and provide concrete evidence "
                        "before proposing a decision."
                    ),
                    reason="Evidence check rule triggered.",
                )

            option_ids = {option.id for option in proposal.options}
            if (
                not proposal.question.strip()
                or proposal.recommendation not in option_ids
                or any(
                    not value.strip()
                    for option in proposal.options
                    for value in (option.id, option.label, option.consequence)
                )
            ):
                return Guide(
                    feedback=(
                        "DecisionProposal options or recommendation are inadequate. "
                        "Investigate the available alternatives and resubmit "
                        "2–4 complete options with a valid recommendation."
                    ),
                    reason="Option quality check triggered.",
                )

            if not self.governor_enabled:
                return self._ask_human(
                    event,
                    proposal,
                    why_human="Baseline mode asks on every valid DecisionProposal.",
                )

            # Deterministic resolution rules:
            # 1. Implementation-only + reversible + low/medium -> AUTO_RESOLVE.
            implementation_only = set(proposal.dimensions) == {"implementation"}
            safe_implementation = (
                implementation_only
                and proposal.impact in {"low", "medium"}
                and proposal.reversible
            )
            # 2. A declared, evidenced frozen constraint determines the choice.
            matching_constraint = (
                proposal.constraint_key is not None
                and proposal.constraint_key in self.frozen_constraints
                and bool(str(self.frozen_constraints[proposal.constraint_key]).strip())
                and (
                    proposal.constraint_key.casefold() in proposal.evidence.casefold()
                    or str(self.frozen_constraints[proposal.constraint_key]).casefold()
                    in proposal.evidence.casefold()
                )
            )

            gate_decision: GateDecision
            if safe_implementation or matching_constraint:
                gate_decision = GateDecision(
                    action="AUTO_RESOLVE",
                    choice_id=proposal.recommendation,
                    reason=(
                        "Deterministic rule: "
                        + (
                            "implementation-only, reversible, low/medium-impact "
                            "decision auto-resolved."
                            if safe_implementation
                            else "matching frozen constraint determines the choice."
                        )
                    ),
                )
            else:
                # All unresolved material dimensions, including security, data,
                # public behavior, and external side effects, go through the Gate.
                gate_decision = self.gate_decider.decide(proposal)

            if gate_decision.action == "AUTO_RESOLVE":
                self.ledger.record_auto_resolve()
                chosen_id = gate_decision.choice_id or proposal.recommendation
                return Guide(
                    feedback=(
                        f"DecisionProposal auto-resolved to choice '{chosen_id}'. "
                        "Continue using that choice and do not ask the same question again."
                    ),
                    reason=gate_decision.reason,
                )

            return self._ask_human(event, proposal, why_human=gate_decision.reason)

        return Proceed(reason="Non-decision tool call is allowed.")

    def _proposal_from_tool_args(self, tool_args: dict[str, Any]) -> DecisionProposal:
        from judgement_call.contracts import DecisionOption

        raw_options = tool_args.get("options", [])
        if not isinstance(raw_options, list):
            raise ValueError("options must be a list")

        options = [
            DecisionOption(
                id=opt.get("id", str(i)),
                label=opt.get("label", ""),
                consequence=opt.get("consequence", ""),
            )
            for i, opt in enumerate(raw_options)
            if isinstance(opt, dict)
        ]
        return DecisionProposal(
            question=tool_args.get("question", ""),
            options=options,
            recommendation=tool_args.get("recommendation", ""),
            dimensions=tool_args.get("dimensions", []),
            impact=tool_args.get("impact", "low"),
            reversible=tool_args.get("reversible", True),
            constraint_key=tool_args.get("constraint_key"),
            evidence=tool_args.get("evidence", ""),
        )

    def _ask_human(
        self,
        event: Any,
        proposal: DecisionProposal,
        why_human: str,
    ) -> Proceed | Guide:
        """Use the raw Strands interrupt lifecycle for a human decision.

        The first call to ``event.interrupt`` raises ``InterruptException`` and
        stops the Strands loop. On resume, the same call returns the human's
        response; only then do we return ``Proceed`` so the original tool call
        continues. This deliberately avoids the Confirm intervention shortcut.
        """
        try:
            response = event.interrupt(self.name, reason=proposal.question)
        except InterruptException as exc:
            self.ledger.record_human_interrupt()
            interrupt_id = exc.interrupt.id
            self.pending_interrupts[interrupt_id] = DecisionCard(
                interrupt_id=interrupt_id,
                question=proposal.question,
                why_human=why_human,
                options=proposal.options,
                recommendation=proposal.recommendation,
                evidence=proposal.evidence,
            )
            raise

        choice_id = response.get("choice_id") if isinstance(response, dict) else response
        if choice_id not in {option.id for option in proposal.options}:
            return Guide(
                feedback=(
                    "The human response did not select one of the proposed options. "
                    "Use the presented Decision Card choices and continue."
                ),
                reason="Invalid human decision response.",
            )

        self._apply_human_choice(event, choice_id)
        return Proceed(reason="Human decision received through raw Strands interrupt.")

    @staticmethod
    def _apply_human_choice(event: Any, choice_id: str) -> None:
        tool_use = getattr(event, "tool_use", None)
        if isinstance(tool_use, dict) and isinstance(tool_use.get("input"), dict):
            tool_use["input"]["recommendation"] = choice_id
            return

        tool_args = getattr(event, "tool_args", None)
        if isinstance(tool_args, dict):
            tool_args["recommendation"] = choice_id
