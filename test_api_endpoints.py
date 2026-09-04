import asyncio
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_routes():
    print("--- Testing API Endpoints ---")
    # 1. Health check
    r = client.get("/api/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health = r.json()
    assert health["status"] == "healthy"
    assert health["python_runnable"] is True
    print("[PASS] GET /api/health")

    # 2. GET index.html
    r = client.get("/")
    assert r.status_code == 200
    assert "RAZE" in r.text
    assert "submission.py" in r.text
    print("[PASS] GET / (Template rendered)")

    # 3. POST /api/run-code
    r = client.post("/api/run-code", json={"language": "python", "code": "print(10 + 25)"})
    assert r.status_code == 200
    exec_res = r.json()
    assert exec_res["executed"] is True
    assert "35" in exec_res["stdout"]
    print("[PASS] POST /api/run-code")

    # 4. POST /api/session/start
    r = client.post("/api/session/start", json={
        "language": "python",
        "code": "x = 42\nprint(xs)",
        "error_message": "",
        "expected_result": "42",
        "actual_result": ""
    })
    assert r.status_code == 200
    sess_data = r.json()
    session_id = sess_data["session_id"]
    assert session_id is not None
    assert sess_data["question_1"] is not None
    print(f"[PASS] POST /api/session/start (Session: {session_id[:8]})")

    # 5. POST /api/session/answer (Q1 -> Q2)
    r = client.post("/api/session/answer", json={
        "session_id": session_id,
        "answer": "Typo on variable xs"
    })
    assert r.status_code == 200
    sess_data_q2 = r.json()
    assert sess_data_q2["question_2"] is not None
    assert sess_data_q2["stage"] == "waiting_answer_2"
    print("[PASS] POST /api/session/answer (Stage: waiting_answer_2)")

    # 6. POST /api/session/answer (Q2 -> Final Solution)
    r = client.post("/api/session/answer", json={
        "session_id": session_id,
        "answer": "Change xs to x"
    })
    assert r.status_code == 200
    sess_data_sol = r.json()
    assert sess_data_sol["stage"] == "completed"
    assert sess_data_sol["is_completed"] is True
    assert sess_data_sol["final_solution"] is not None
    print("[PASS] POST /api/session/answer (STOP RULE: Completed, Solution delivered)")

    # 7. GET /api/session/{session_id}
    r = client.get(f"/api/session/{session_id}")
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id
    print("[PASS] GET /api/session/{session_id}")

    # 8. POST /api/session/reset
    r = client.post("/api/session/reset", json={"session_id": session_id})
    assert r.status_code == 200
    print("[PASS] POST /api/session/reset")

    # 9. Verify session is deleted
    r = client.get(f"/api/session/{session_id}")
    assert r.status_code == 404
    print("[PASS] Verified session deleted after reset")

    print("\n>>> ALL API ENDPOINTS VERIFIED AND PASSING! <<<")

if __name__ == "__main__":
    test_routes()

