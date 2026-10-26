import json
import shutil
from pathlib import Path

import pytest

from studies import attempts
from studies.db import connect
from studies.normalize import load_certification
from studies.text import option_to_markdown

CERT = Path("data/certifications/aws-certified-gen-ai-developer")
EXAM = 7310851


@pytest.fixture
def conn(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    c = connect(":memory:")
    load_certification(c, dest)
    return c


def _correct(conn, attempt_id, position):
    row = attempts.attempt_questions(conn, attempt_id)[position - 1]
    return row["id"], json.loads(row["correct_json"])


def test_start_snapshots_all_questions(conn):
    a = attempts.start_attempt(conn, EXAM)
    assert attempts.summary(conn, a) == {"total": 75, "correct": 0, "wrong": 0, "skipped": 75}
    assert attempts.first_unanswered(conn, a) == 1


def test_answer_correctness_and_optional_fields(conn):
    a = attempts.start_attempt(conn, EXAM)
    rev, correct = _correct(conn, a, 1)
    assert attempts.record_answer(conn, a, rev, list(reversed(correct))) is True
    rev2, correct2 = _correct(conn, a, 2)
    wrong = ["a"] if correct2 != ["a"] else ["b"]
    assert attempts.record_answer(conn, a, rev2, wrong, confidence="guess", reasoning="  chutei ", time_seconds=12.5) is False
    s = attempts.summary(conn, a)
    assert (s["correct"], s["wrong"], s["skipped"]) == (1, 1, 73)
    row = attempts.attempt_questions(conn, a)[1]
    assert row["confidence"] == "guess" and row["reasoning"] == "chutei"
    assert attempts.first_unanswered(conn, a) == 3


def test_multi_select_needs_exact_set(conn):
    a = attempts.start_attempt(conn, EXAM)
    rows = attempts.attempt_questions(conn, a)
    multi = next(r for r in rows if r["assessment_type"] == "multi-select")
    correct = json.loads(multi["correct_json"])
    assert attempts.record_answer(conn, a, multi["id"], correct[:-1]) is False


def test_cannot_answer_twice_or_after_finish(conn):
    a = attempts.start_attempt(conn, EXAM)
    rev, correct = _correct(conn, a, 1)
    attempts.record_answer(conn, a, rev, correct)
    with pytest.raises(Exception):
        attempts.record_answer(conn, a, rev, correct)
    attempts.finish_attempt(conn, a)
    rev2, correct2 = _correct(conn, a, 2)
    with pytest.raises(ValueError):
        attempts.record_answer(conn, a, rev2, correct2)


def test_invalid_confidence_and_empty_selection(conn):
    a = attempts.start_attempt(conn, EXAM)
    rev, correct = _correct(conn, a, 1)
    with pytest.raises(ValueError):
        attempts.record_answer(conn, a, rev, correct, confidence="certeza")
    with pytest.raises(ValueError):
        attempts.record_answer(conn, a, rev, [])


def test_resume_lists_in_progress_only(conn):
    a = attempts.start_attempt(conn, EXAM)
    b = attempts.start_attempt(conn, EXAM)
    attempts.abandon_attempt(conn, b)
    assert [r["id"] for r in attempts.in_progress_attempts(conn)] == [a]


def test_attempt_pins_revision_after_content_changes(conn):
    a = attempts.start_attempt(conn, EXAM)
    pinned = attempts.attempt_questions(conn, a)[0]["id"]
    conn.execute(
        "INSERT INTO question_revision (question_id, content_hash, assessment_type, section_id, prompt_html, "
        "explanation_html, options_json, correct_json, links_json, first_seen_at, last_seen_at) "
        "SELECT question_id, 'novo', assessment_type, section_id, prompt_html, explanation_html, options_json, "
        "correct_json, links_json, '2999', '2999' FROM question_revision WHERE id = ?", (pinned,))
    assert attempts.attempt_questions(conn, a)[0]["id"] == pinned
    assert attempts.latest_revisions(conn, EXAM)[0] != pinned


def test_ai_reasoning_lives_on_revision(conn):
    rev = attempts.latest_revisions(conn, EXAM)[0]
    attempts.set_ai_reasoning(conn, rev, " texto do Gemini ")
    assert conn.execute("SELECT ai_reasoning FROM question_revision WHERE id=?", (rev,)).fetchone()[0] == "texto do Gemini"


def test_option_to_markdown():
    assert option_to_markdown("<p>Use <code>IsComplete</code> &amp; more</p>") == "Use `IsComplete` & more"


def test_permutation_translation_roundtrip():
    perm = [2, 0, 3, 1]  # tela a,b,c,d mostra originais c,a,d,b
    assert attempts.to_original(["a", "d"], perm) == ["b", "c"]
    assert attempts.to_display(["b", "c"], perm) == ["a", "d"]
    for letters in (["a"], ["b", "c"], ["a", "b", "d"]):
        assert attempts.to_display(attempts.to_original(letters, perm), perm) == letters
    assert attempts.to_original(["c", "a"], None) == ["a", "c"]


def test_shuffle_stores_permutation_per_question(conn):
    import random
    a = attempts.start_attempt(conn, EXAM, shuffle=True, rng=random.Random(1))
    rows = attempts.attempt_questions(conn, a)
    assert conn.execute("SELECT shuffle FROM attempt WHERE id=?", (a,)).fetchone()[0] == 1
    for r in rows:
        perm = json.loads(r["permutation_json"])
        assert sorted(perm) == list(range(len(json.loads(r["options_json"]))))
    assert any(json.loads(r["permutation_json"]) != sorted(json.loads(r["permutation_json"])) for r in rows)
    plain = attempts.start_attempt(conn, EXAM)
    assert all(r["permutation_json"] is None for r in attempts.attempt_questions(conn, plain))


def test_exam_mode_allows_changing_answer_until_finish(conn):
    a = attempts.start_attempt(conn, EXAM, mode="exam")
    rev, correct = _correct(conn, a, 1)
    wrong = ["a"] if correct != ["a"] else ["b"]
    assert attempts.record_answer(conn, a, rev, wrong) is False
    assert attempts.record_answer(conn, a, rev, correct, confidence="confident") is True
    s = attempts.summary(conn, a)
    assert (s["correct"], s["wrong"]) == (1, 0)
    assert conn.execute("SELECT count(*) FROM answer WHERE attempt_id=?", (a,)).fetchone()[0] == 1
    attempts.finish_attempt(conn, a)
    with pytest.raises(ValueError):
        attempts.record_answer(conn, a, rev, wrong)
