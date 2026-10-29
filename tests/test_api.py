import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from studies import api
from studies.db import connect
from studies.normalize import load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")
EXAM = 7310851
H = {"Authorization": "Bearer segredo"}


@pytest.fixture
def client(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    conn = connect(":memory:", check_same_thread=False)
    load_certification(conn, dest)
    with TestClient(api.create_app(conn, token="segredo")) as c:
        c.conn = conn
        yield c


def correct_of(client, attempt_id, position):
    """Gabarito em letras exibidas, lido direto do banco (a API não o entrega antes da hora)."""
    from studies import attempts
    r = attempts.attempt_questions(client.conn, attempt_id)[position - 1]
    perm = json.loads(r["permutation_json"]) if r["permutation_json"] else None
    return attempts.to_display(json.loads(r["correct_json"]), perm)


def test_requires_token_but_health_is_open(client):
    assert client.get("/health").json() == {"ok": True}
    assert client.get("/certifications").status_code == 401
    assert client.get("/certifications", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert client.get("/certifications", headers=H).status_code == 200


def test_app_refuses_to_start_without_token(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        api.create_app()


def test_exam_mode_never_leaks_answer_key_until_finished(client):
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM, "mode": "exam"}, headers=H).json()["attempt_id"]
    q = client.get(f"/attempts/{a}/questions/1", headers=H).json()
    assert not q["reveal"] and "correct" not in q and "explanation_html" not in q
    r = client.post(f"/attempts/{a}/answers", json={"position": 1, "selected": correct_of(client, a, 1)}, headers=H).json()
    assert r["is_correct"] is None  # Exam mode não revela
    assert all(m["is_correct"] is None for m in client.get(f"/attempts/{a}", headers=H).json()["map"])
    assert "correct" not in client.get(f"/attempts/{a}/questions/1", headers=H).json()
    client.post(f"/attempts/{a}/finish", headers=H)
    q = client.get(f"/attempts/{a}/questions/1", headers=H).json()
    assert q["reveal"] and q["is_correct"] is True and q["explanation_html"]


def test_practice_reveals_after_answer_and_blocks_a_second_answer(client):
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM}, headers=H).json()["attempt_id"]
    assert "correct" not in client.get(f"/attempts/{a}/questions/1", headers=H).json()
    body = {"position": 1, "selected": correct_of(client, a, 1), "confidence": "confident"}
    assert client.post(f"/attempts/{a}/answers", json=body, headers=H).json()["is_correct"] is True
    q = client.get(f"/attempts/{a}/questions/1", headers=H).json()
    assert q["reveal"] and q["correct"] == body["selected"] and q["confidence"] == "confident"
    assert client.post(f"/attempts/{a}/answers", json=body, headers=H).status_code == 409


def test_score_has_pass_math_for_exams_only(client):
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM}, headers=H).json()["attempt_id"]
    for pos in range(1, 4):
        client.post(f"/attempts/{a}/answers", json={"position": pos, "selected": correct_of(client, a, pos)}, headers=H)
    s = client.get(f"/attempts/{a}", headers=H).json()["score"]
    assert (s["correct"], s["wrong"], s["skipped"], s["total"]) == (3, 0, 72, 75)
    assert s["pass"]["needed"] == 57 and s["pass"]["still_needed"] == 54 and not s["pass"]["failed"]
    fin = client.post(f"/attempts/{a}/finish", headers=H).json()
    assert fin["state"] == "finished" and fin["score"]["pass"]["failed"]  # puladas viram erros

    sec = client.conn.execute("SELECT id, certification_id FROM section LIMIT 1").fetchone()
    d = client.post("/attempts", json={"kind": "drill", "certification_id": sec[1], "section_id": sec[0], "n": 5}, headers=H)
    assert d.status_code == 201
    assert client.get(f"/attempts/{d.json()['attempt_id']}", headers=H).json()["score"]["pass"] is None


def test_shuffled_answers_are_in_displayed_letters(client):
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM, "shuffle": True}, headers=H).json()["attempt_id"]
    for pos in (1, 2, 3):
        r = client.post(f"/attempts/{a}/answers", json={"position": pos, "selected": correct_of(client, a, pos)}, headers=H)
        assert r.json()["is_correct"] is True


def test_validation_errors(client):
    assert client.post("/attempts", json={"kind": "exam"}, headers=H).status_code == 422
    assert client.post("/attempts", json={"kind": "review", "certification_id": 1, "filter": "x"}, headers=H).status_code == 422
    assert client.get("/attempts/999", headers=H).status_code == 404
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM}, headers=H).json()["attempt_id"]
    assert client.get(f"/attempts/{a}/questions/999", headers=H).status_code == 404
    assert client.post(f"/attempts/{a}/answers", json={"position": 1, "selected": []}, headers=H).status_code == 422
    assert client.post(f"/attempts/{a}/answers", json={"position": 1, "selected": ["a"], "confidence": "x"}, headers=H).status_code == 422


def test_dashboard_with_and_without_data(client):
    cert = client.get("/certifications", headers=H).json()[0]["id"]
    empty = client.get(f"/dashboard/{cert}", headers=H).json()
    assert empty["answers"] == 0 and empty["streaks"]["current"] == 0 and not empty["readiness"]["ready"]
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM}, headers=H).json()["attempt_id"]
    for pos in range(1, 6):
        sel = correct_of(client, a, pos)
        client.post(f"/attempts/{a}/answers", json={"position": pos, "selected": sel if pos != 3 else ["a"] if sel != ["a"] else ["b"]}, headers=H)
    client.post(f"/attempts/{a}/finish", headers=H)
    d = client.get(f"/dashboard/{cert}", headers=H).json()
    assert d["answers"] == 5 and d["streaks"]["longest_correct"] == 2 and d["streaks"]["current"] == 2
    assert len(d["scores"]) == 1 and d["calibration"]
    assert d["accuracy_new"] is not None and d["progression"] and d["by"]["section"] and d["pace"]["days"]
    assert d["most_wrong"] and d["consistency_by_section"] and "nodes" in d["topics"]
    w = client.get(f"/dashboard/{cert}?window=7d&freq=W&roll=2", headers=H).json()
    assert w["answers"] == 5 and w["window"]["start"] < w["window"]["end"]


def test_priority_review_follows_risk_order(client):
    cert = client.get("/certifications", headers=H).json()[0]["id"]
    body = {"kind": "review", "certification_id": cert, "filter": "priority", "n": 5}
    assert client.post("/attempts", json=body, headers=H).status_code == 409  # nada a revisar ainda
    a = client.post("/attempts", json={"kind": "exam", "exam_id": EXAM}, headers=H).json()["attempt_id"]
    for pos in range(1, 6):
        sel = correct_of(client, a, pos)
        wrong = ["a"] if sel != ["a"] else ["b"]
        client.post(f"/attempts/{a}/answers", json={"position": pos, "selected": wrong,
                                                    "confidence": "confident" if pos == 4 else None}, headers=H)
    client.post(f"/attempts/{a}/finish", headers=H)
    r = client.post("/attempts", json=body, headers=H)
    assert r.status_code == 201
    review = client.get(f"/attempts/{r.json()['attempt_id']}", headers=H).json()
    assert review["kind"] == "review" and len(review["map"]) == 5
    first = client.get(f"/attempts/{r.json()['attempt_id']}/questions/1", headers=H).json()
    # a Question errada com confiança (pos 4) pesa mais e vem primeiro
    orig = client.get(f"/attempts/{a}/questions/4", headers=H).json()
    assert first["prompt_html"] == orig["prompt_html"]
