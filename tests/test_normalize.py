import json
import shutil
from pathlib import Path

import pytest

from studies.db import connect
from studies.normalize import canonical_section, content_hash, load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")


@pytest.fixture
def cert_dir(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    return dest


def test_loads_all_questions(cert_dir):
    conn = connect(":memory:")
    stats = load_certification(conn, cert_dir)
    assert {k: stats[k] for k in ("questions", "new_revisions", "skipped")} == {"questions": 975, "new_revisions": 975, "skipped": 0}
    assert conn.execute("SELECT count(*) FROM exam").fetchone()[0] == 13
    assert conn.execute("SELECT count(*) FROM section").fetchone()[0] == 5
    types = {r[0] for r in conn.execute("SELECT DISTINCT assessment_type FROM question_revision")}
    assert types == {"multiple-choice", "multi-select"}


def test_reload_is_idempotent(cert_dir):
    conn = connect(":memory:")
    load_certification(conn, cert_dir)
    stats = load_certification(conn, cert_dir)
    assert stats["new_revisions"] == 0
    assert conn.execute("SELECT count(*) FROM question_revision").fetchone()[0] == 975
    assert conn.execute("SELECT count(*) FROM question").fetchone()[0] == 975


def test_changed_content_creates_new_revision(cert_dir):
    conn = connect(":memory:")
    load_certification(conn, cert_dir)
    path = cert_dir / "raw" / "mock-exams" / "7310851.json"
    raw = json.loads(path.read_text())
    qid = raw["results"][0]["id"]
    raw["results"][0]["prompt"]["explanation"] += "<p>editado</p>"
    path.write_text(json.dumps(raw))
    stats = load_certification(conn, cert_dir)
    assert stats["new_revisions"] == 1
    n = conn.execute(
        "SELECT count(*) FROM question_revision r JOIN question q ON q.id=r.question_id WHERE q.udemy_id=?",
        (qid,),
    ).fetchone()[0]
    assert n == 2


def test_hash_ignores_correct_response_order():
    item = {
        "assessment_type": "multi-select",
        "prompt": {"question": "q", "answers": ["a", "b"], "explanation": "e"},
        "correct_response": ["b", "a"],
    }
    swapped = {**item, "correct_response": ["a", "b"]}
    assert content_hash(item, "s") == content_hash(swapped, "s")


def test_unmapped_section_fails_loudly():
    with pytest.raises(ValueError):
        canonical_section("Outra coisa", {"X": ["x"]})


def test_exam_label_is_stored_and_falls_back_to_title(cert_dir):
    cfg_path = cert_dir / "certification.json"
    cfg = json.loads(cfg_path.read_text())
    first, second = cfg["courses"]["mock-exams"]["quizzes"][:2]
    first["label"] = "Exam 1"
    second.pop("label", None)
    cfg_path.write_text(json.dumps(cfg))
    conn = connect(":memory:")
    load_certification(conn, cert_dir)
    rows = {r["id"]: r for r in conn.execute("SELECT id, title, label FROM exam")}
    assert rows[first["id"]]["label"] == "Exam 1"
    assert rows[second["id"]]["label"] is None
    shown = conn.execute("SELECT COALESCE(label, title) FROM exam WHERE id=?", (second["id"],)).fetchone()[0]
    assert shown == second["title"]


def test_old_database_without_label_column_is_migrated(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE exam (id INTEGER PRIMARY KEY, course_id INTEGER, position INTEGER, title TEXT NOT NULL, udemy_version INTEGER)")
    old.execute("INSERT INTO exam VALUES (1, 1, 1, 'T', 3)")
    old.commit()
    old.close()
    conn = connect(path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exam)")}
    assert "label" in cols
    assert conn.execute("SELECT title, label FROM exam").fetchone()[:] == ("T", None)
    connect(path)  # idempotente: abrir de novo não falha
