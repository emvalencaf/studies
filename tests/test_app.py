import json
import shutil
from pathlib import Path

from streamlit.testing.v1 import AppTest

from studies.db import connect
from studies.normalize import load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")


def test_full_flow_in_practice_mode(tmp_path, monkeypatch):
    db = tmp_path / "studies.db"
    cert = tmp_path / CERT.name
    shutil.copytree(CERT, cert)
    load_certification(connect(db), cert)
    monkeypatch.setenv("STUDIES_DB", str(db))

    at = AppTest.from_file(str(Path(__file__).parent.parent / "src/studies/app.py"), default_timeout=30).run()
    assert not at.exception
    next(b for b in at.button if b.label == "Iniciar Exam").click().run()
    assert "Questão 1/75" in at.get("progress")[0].proto.text
    at.radio[0].set_value("a").run()
    next(b for b in at.button if b.label == "Confirmar").click().run()
    assert not at.exception
    assert any(m.value in ("Correto", "Errado") for m in list(at.success) + list(at.error))

    n = connect(db).execute("SELECT count(*) FROM answer").fetchone()[0]
    assert n == 1


def _setup(tmp_path, monkeypatch):
    db = tmp_path / "studies.db"
    cert = tmp_path / CERT.name
    shutil.copytree(CERT, cert)
    load_certification(connect(db), cert)
    monkeypatch.setenv("STUDIES_DB", str(db))
    return db, AppTest.from_file(str(Path(__file__).parent.parent / "src/studies/app.py"), default_timeout=30)


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def test_exam_mode_hides_feedback_until_finish(tmp_path, monkeypatch):
    db, at = _setup(tmp_path, monkeypatch)
    at.run()
    at.radio[0].set_value("exam").run()
    _button(at, "Iniciar Exam").click().run()
    at.radio[0].set_value("a").run()
    _button(at, "Confirmar").click().run()
    assert not at.exception
    assert not list(at.success) and not list(at.error)  # sem gabarito durante a prova
    assert any("registrada" in c.value for c in at.caption)
    _button(at, "Finalizar Attempt").click().run()
    assert not at.exception
    assert list(at.success) or list(at.error)  # gabarito liberado
    assert connect(db).execute("SELECT mode, state FROM attempt").fetchone()[:] == ("exam", "finished")


def test_shuffled_answer_is_stored_in_original_letters(tmp_path, monkeypatch):
    db, at = _setup(tmp_path, monkeypatch)
    at.run()
    at.checkbox[0].check()
    _button(at, "Iniciar Exam").click().run()
    row = connect(db).execute("SELECT permutation_json FROM attempt_question WHERE position=1").fetchone()
    assert row[0] is not None
    perm = json.loads(row[0])
    at.radio[0].set_value("a").run()
    _button(at, "Confirmar").click().run()
    assert not at.exception
    stored = json.loads(connect(db).execute("SELECT selected_json FROM answer").fetchone()[0])
    assert stored == [attempts_letters[perm[0]]]


attempts_letters = "abcdefghij"


def test_drill_from_ui_creates_attempt_without_exam(tmp_path, monkeypatch):
    db, at = _setup(tmp_path, monkeypatch)
    at.run()
    assert not at.exception
    at.number_input[0].set_value(5).run()
    _button(at, "Iniciar Drill").click().run()
    assert not at.exception
    kind, exam_id = connect(db).execute("SELECT kind, exam_id FROM attempt").fetchone()[:]
    assert (kind, exam_id) == ("drill", None)
    assert connect(db).execute("SELECT count(*) FROM attempt_question").fetchone()[0] == 5
    assert "Questão 1/5" in at.get("progress")[0].proto.text


def test_review_button_disabled_without_history(tmp_path, monkeypatch):
    db, at = _setup(tmp_path, monkeypatch)
    at.run()
    assert _button(at, "Iniciar Review").disabled


def test_dashboard_renders_empty_and_with_data(tmp_path, monkeypatch):
    db, at = _setup(tmp_path, monkeypatch)
    at.run()
    at.sidebar.radio[0].set_value("Dashboard").run()
    assert not at.exception
    assert any("Nenhuma Answer" in i.value for i in at.info)

    # um Exam finalizado com algumas respostas
    from studies import attempts as att
    conn = connect(db)
    a = att.start_attempt(conn, 7310851)
    rows = att.attempt_questions(conn, a)
    for r in rows[:12]:
        att.record_answer(conn, a, r["id"], json.loads(r["correct_json"]) if r["position"] % 3 else ["a"], "confident" if r["position"] % 2 else None, time_seconds=20)
    att.finish_attempt(conn, a)
    conn.close()

    at2 = AppTest.from_file(str(Path(__file__).parent.parent / "src/studies/app.py"), default_timeout=60).run()
    at2.sidebar.radio[0].set_value("Dashboard").run()
    assert not at2.exception, at2.exception
    assert len(at2.tabs) == 7
    labels = [m.label for m in at2.metric]
    assert "Acerto na janela" in labels and "Melhor nota" in labels
