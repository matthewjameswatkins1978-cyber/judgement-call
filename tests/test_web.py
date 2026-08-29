from unittest.mock import patch

from fastapi.testclient import TestClient

from judgement_call.contracts import (
    AttentionReceipt,
    CompletedResponse,
    DecisionCard,
    DecisionOption,
    NeedsHumanResponse,
)
from judgement_call.web import app, service

client = TestClient(app)


def test_get_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "JUDGEMENT CALL" in response.text


@patch.object(service, "start")
def test_api_start(mock_start):
    mock_start.return_value = CompletedResponse(
        run_id="run-123",
        summary="Success",
        diff="diff content",
        verification="PASS",
        receipt=AttentionReceipt(final_verifier_passed=True),
    )

    response = client.post(
        "/api/start",
        json={
            "op": "start",
            "scenario": "concurrency-demo",
            "task": "Make process_items execute concurrently",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["run_id"] == "run-123"
    assert data["verification"] == "PASS"


@patch.object(service, "resume")
def test_api_resume(mock_resume):
    mock_resume.return_value = NeedsHumanResponse(
        run_id="run-123",
        decision=DecisionCard(
            interrupt_id="int-1",
            question="Which strategy?",
            why_human="Ambiguous",
            options=[
                DecisionOption(id="A", label="A", consequence="A"),
                DecisionOption(id="B", label="B", consequence="B"),
            ],
            recommendation="A",
            evidence="Ev",
        ),
        receipt=AttentionReceipt(),
    )

    response = client.post(
        "/api/resume",
        json={
            "op": "resume",
            "interrupt_id": "int-1",
            "response": {"choice_id": "A", "note": "Looks good"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_human"
    assert data["decision"]["interrupt_id"] == "int-1"


def test_api_validation_error_start():
    # Missing required fields or invalid op
    response = client.post(
        "/api/start",
        json={
            "op": "invalid",
            "scenario": "concurrency-demo",
            "task": "",
        },
    )
    assert response.status_code == 422


def test_api_validation_error_resume():
    response = client.post(
        "/api/resume",
        json={
            "op": "invalid",
        },
    )
    assert response.status_code == 422
