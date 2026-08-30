from enum import StrEnum
from typing import Literal, Union

from pydantic import BaseModel, Field, model_validator


class Scenario(StrEnum):
    CONCURRENCY_DEMO = "concurrency-demo"


class Dimensions(StrEnum):
    IMPLEMENTATION = "implementation"
    PUBLIC_BEHAVIOR = "public_behavior"
    SECURITY = "security"
    COST = "cost"
    DATA = "data"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


class Impact(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GateAction(StrEnum):
    AUTO_RESOLVE = "AUTO_RESOLVE"
    ASK_HUMAN = "ASK_HUMAN"


class FailureCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_SESSION = "INVALID_SESSION"
    WORKSPACE_ERROR = "WORKSPACE_ERROR"
    POLICY_DENIED = "POLICY_DENIED"
    MODEL_ERROR = "MODEL_ERROR"
    TOOL_LIMIT = "TOOL_LIMIT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DecisionOption(BaseModel):
    id: str
    label: str
    consequence: str


class DecisionProposal(BaseModel):
    question: str
    options: list[DecisionOption]
    recommendation: str
    dimensions: list[str]
    impact: str
    reversible: bool
    constraint_key: str | None = None
    evidence: str

    @model_validator(mode="after")
    def validate_options_and_impact_and_dimensions(self) -> "DecisionProposal":
        if not (2 <= len(self.options) <= 4):
            raise ValueError("DecisionProposal options must have between 2 and 4 items")

        # Validate impact against Impact enum values
        valid_impacts = {i.value for i in Impact}
        if self.impact not in valid_impacts:
            raise ValueError(f"Invalid impact: {self.impact}. Must be one of {valid_impacts}")

        # Validate dimensions against Dimensions enum values
        valid_dims = {d.value for d in Dimensions}
        for dim in self.dimensions:
            if dim not in valid_dims:
                raise ValueError(f"Invalid dimension: {dim}. Must be one of {valid_dims}")

        return self


class GateDecision(BaseModel):
    action: Literal['AUTO_RESOLVE', 'ASK_HUMAN']
    choice_id: str | None = None
    reason: str


class DecisionCard(BaseModel):
    interrupt_id: str
    question: str
    why_human: str
    options: list[DecisionOption]
    recommendation: str
    evidence: str


class AttentionReceipt(BaseModel):
    decision_proposals: int = 0
    auto_resolved: int = 0
    human_interrupts: int = 0
    policy_denials: int = 0
    tool_calls: int = 0
    test_runs: int = 0
    final_verifier_passed: bool = False


class ResumeChoice(BaseModel):
    choice_id: str
    note: str | None = None


class StartRequest(BaseModel):
    op: Literal['start']
    scenario: Literal['concurrency-demo']
    task: str = Field(..., min_length=1, max_length=4000)


class ResumeRequest(BaseModel):
    op: Literal['resume']
    interrupt_id: str
    response: ResumeChoice


class TaskContract(BaseModel):
    scenario: str = 'concurrency-demo'
    allowed_paths: list[str]
    protected_paths: list[str]
    acceptance_command: str
    frozen_constraints: dict[str, str]


class CompletedResponse(BaseModel):
    status: Literal['completed'] = 'completed'
    run_id: str
    summary: str
    diff: str
    verification: str
    receipt: AttentionReceipt


class NeedsHumanResponse(BaseModel):
    status: Literal['needs_human'] = 'needs_human'
    run_id: str
    decision: DecisionCard
    receipt: AttentionReceipt


class FailureResponse(BaseModel):
    status: Literal['failed'] = 'failed'
    run_id: str
    code: FailureCode
    message: str
    receipt: AttentionReceipt


RunResponse = Union[CompletedResponse, NeedsHumanResponse, FailureResponse]
