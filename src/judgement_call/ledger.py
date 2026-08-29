from judgement_call.contracts import AttentionReceipt


class RunLedger:
    def __init__(self) -> None:
        self._decision_proposals = 0
        self._auto_resolved = 0
        self._human_interrupts = 0
        self._policy_denials = 0
        self._tool_calls = 0
        self._test_runs = 0
        self._final_verifier_passed = False

    def record_tool_call(self) -> None:
        self._tool_calls += 1

    def record_decision_proposal(self) -> None:
        self._decision_proposals += 1

    def record_auto_resolve(self) -> None:
        self._auto_resolved += 1

    def record_human_interrupt(self) -> None:
        self._human_interrupts += 1

    def record_policy_denial(self) -> None:
        self._policy_denials += 1

    def record_test_run(self) -> None:
        self._test_runs += 1

    def set_final_verifier(self, passed: bool) -> None:
        self._final_verifier_passed = passed

    def receipt(self) -> AttentionReceipt:
        return AttentionReceipt(
            decision_proposals=self._decision_proposals,
            auto_resolved=self._auto_resolved,
            human_interrupts=self._human_interrupts,
            policy_denials=self._policy_denials,
            tool_calls=self._tool_calls,
            test_runs=self._test_runs,
            final_verifier_passed=self._final_verifier_passed,
        )
