import pytest
from fastapi.testclient import TestClient
from app import create_app
from security.security import SecurityConfig

# Create a test client
security_config = SecurityConfig()
app = create_app(security_config)
client = TestClient(app)

@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client

def test_health_check(test_client):
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "auth_mode": security_config.AUTH_MODE,
        "rag_system": "initialized"
    }

def test_upload_document(test_client):
    with open("tests/sample.pdf", "rb") as file:
        response = test_client.post("/upload_document", files={"file": file})
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Document processed successfully"

def test_ask_question(test_client):
    question = {"question": "What is the topic for Week 1?"}
    response = test_client.post("/ask_question", json=question)
    assert response.status_code == 200
    assert "answer" in response.json()
    assert "question" in response.json()
    assert response.json()["question"] == question["question"]

def test_get_metrics(test_client):
    response = test_client.get("/metrics")
    assert response.status_code == 200
    assert "avg_response_time" in response.json()
    assert "avg_relevance_score" in response.json()
    assert "current_temperature" in response.json()
    assert "temperature_history" in response.json()