import logging
from typing import Any

from strands.interventions import InterventionHandler
from strands.interventions.actions import Confirm, Guide, Proceed

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
        on_error: str = "throw",
    ) -> None:
        self.ledger = ledger
        self.gate_decider = gate_decider or StrandsGateDecider()
        self.governor_enabled = governor_enabled
        self._on_error = on_error
        self.pending_interrupts: dict[str, DecisionCard] = {}

    @property
    def on_error(self) -> str:
        return self._on_error

    def before_tool_call(self, event: Any, **kwargs: Any) -> Any:
        tool_name = getattr(event, "tool_name", None) or getattr(event, "name", None)
        tool_args = getattr(event, "tool_args", None) or getattr(event, "arguments", {})

        self.ledger.record_tool_call()

        if tool_name == "request_decision":
            self.ledger.record_decision_proposal()

            # Baseline mode check: governor_enabled = False means
            # baseline mode (asks on every decision proposal).
            if not self.governor_enabled:
                self.ledger.record_human_interrupt()
                interrupt_id = f"int-{self.ledger.receipt().human_interrupts}"
                question = tool_args.get("question", "Decision required")
                raw_options = tool_args.get("options", [])
                from judgement_call.contracts import DecisionOption
                options = [
                    DecisionOption(
                        id=opt.get("id", str(i)),
                        label=opt.get("label", ""),
                        consequence=opt.get("consequence", ""),
                    )
                    for i, opt in enumerate(raw_options)
                ]
                recommendation = tool_args.get(
                    "recommendation", options[0].id if options else "A"
                )
                evidence = tool_args.get("evidence", "")

                card = DecisionCard(
                    interrupt_id=interrupt_id,
                    question=question,
                    why_human="Baseline mode asks on every DecisionProposal.",
                    options=options,
                    recommendation=recommendation,
                    evidence=evidence,
                )
                self.pending_interrupts[interrupt_id] = card
                return Confirm(
                    prompt=question,
                    reason="Baseline mode forces human interruption.",
                    response=interrupt_id,
                )

            # Extract proposal from tool_args
            try:
                question = tool_args.get("question", "")
                raw_options = tool_args.get("options", [])
                from judgement_call.contracts import DecisionOption
                options = [
                    DecisionOption(
                        id=opt.get("id", str(i)),
                        label=opt.get("label", ""),
                        consequence=opt.get("consequence", ""),
                    )
                    for i, opt in enumerate(raw_options)
                ]
                recommendation = tool_args.get("recommendation", "")
                dimensions = tool_args.get("dimensions", [])
                impact = tool_args.get("impact", "low")
                reversible = tool_args.get("reversible", True)
                constraint_key = tool_args.get("constraint_key")
                evidence = tool_args.get("evidence", "")

                # Evidence check rule: if evidence is missing/empty, guide agent
                if not evidence or not evidence.strip():
                    return Guide(
                        feedback=(
                            "DecisionProposal missing required evidence. "
                            "Please provide concrete evidence before proposing decisions."
                        ),
                        reason="Evidence check rule triggered.",
                    )

                proposal = DecisionProposal(
                    question=question,
                    options=options,
                    recommendation=recommendation,
                    dimensions=dimensions,
                    impact=impact,
                    reversible=reversible,
                    constraint_key=constraint_key,
                    evidence=evidence,
                )
            except Exception as e:
                return Guide(
                    feedback=f"Invalid DecisionProposal structure: {e}",
                    reason="Validation failed.",
                )

            # Deterministic resolution rules:
            # 1. Low impact + reversible + implementation dimension -> AUTO_RESOLVE
            is_low_impact = proposal.impact == "low"
            is_reversible = proposal.reversible
            is_impl_dim = any(
                "implementation" in str(d).lower() for d in proposal.dimensions
            )

            gate_decision: GateDecision
            if is_low_impact and is_reversible and is_impl_dim:
                gate_decision = GateDecision(
                    action="AUTO_RESOLVE",
                    choice_id=proposal.recommendation,
                    reason=(
                        "Deterministic rule: low impact, reversible "
                        "implementation decision auto-resolved."
                    ),
                )
            else:
                # Fallback to GateDecider (Gate Agent or heuristic)
                gate_decision = self.gate_decider.decide(proposal)

            if gate_decision.action == "AUTO_RESOLVE":
                self.ledger.record_auto_resolve()
                chosen_id = gate_decision.choice_id or proposal.recommendation
                return Confirm(
                    prompt=proposal.question,
                    reason=gate_decision.reason,
                    response=chosen_id,
                )
            else:
                self.ledger.record_human_interrupt()
                interrupt_id = f"int-{self.ledger.receipt().human_interrupts}"
                card = DecisionCard(
                    interrupt_id=interrupt_id,
                    question=proposal.question,
                    why_human=gate_decision.reason,
                    options=proposal.options,
                    recommendation=proposal.recommendation,
                    evidence=proposal.evidence,
                )
                self.pending_interrupts[interrupt_id] = card
                return Confirm(
                    prompt=proposal.question,
                    reason=gate_decision.reason,
                    response=interrupt_id,
                )

        return Proceed()
