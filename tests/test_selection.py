import json
import random
import shutil
from pathlib import Path

import pytest

from studies import attempts, selection
from studies.db import connect
from studies.normalize import load_certification

CERT = Path("data/certifications/aws-certified-gen-ai-developer")
EXAM = 7310851


@pytest.fixture
def conn(tmp_path):
    dest = tmp_path / CERT.name
    shutil.copytree(CERT, dest)
    c = connect(":memory:")
    load_certification(c, dest)
    return c


def _cert(conn):
    return conn.execute("SELECT id FROM certification").fetchone()[0]


def _answer(conn, attempt, position, right: bool, confidence=None):
    row = attempts.attempt_questions(conn, attempt)[position - 1]
    correct = json.loads(row["correct_json"])
    wrong = ["a"] if correct != ["a"] else ["b"]
    attempts.record_answer(conn, attempt, row["id"], correct if right else wrong, confidence)
    return row["id"]


def test_review_filters(conn):
    cert = _cert(conn)
    a1 = attempts.start_attempt(conn, EXAM)
    wrong1 = _answer(conn, a1, 1, False)
    lucky = _answer(conn, a1, 2, True, "guess")
    unmarked = _answer(conn, a1, 3, True)
    attempts.finish_attempt(conn, a1)
    a2 = attempts.start_attempt(conn, EXAM)
    wrong2 = _answer(conn, a2, 4, False, "confident")
    attempts.finish_attempt(conn, a2)

    assert selection.review_questions(conn, cert, "last_wrong") == [wrong2]
    assert selection.review_questions(conn, cert, "any_wrong") == [wrong1, wrong2]
    assert selection.review_questions(conn, cert, "lucky_guess") == [lucky]
    assert selection.review_questions(conn, cert, "no_confidence") == [wrong1, unmarked]
    with pytest.raises(ValueError):
        selection.review_questions(conn, cert, "xyz")


def test_review_ignores_unfinished_attempt_for_last_wrong(conn):
    cert = _cert(conn)
    a1 = attempts.start_attempt(conn, EXAM)
    wrong = _answer(conn, a1, 1, False)
    attempts.finish_attempt(conn, a1)
    a2 = attempts.start_attempt(conn, EXAM)
    _answer(conn, a2, 2, False)  # em andamento: não conta como "último"
    assert selection.review_questions(conn, cert, "last_wrong") == [wrong]


def test_review_attempt_is_not_tied_to_an_exam(conn):
    cert = _cert(conn)
    a1 = attempts.start_attempt(conn, EXAM)
    wrong = _answer(conn, a1, 1, False)
    attempts.finish_attempt(conn, a1)
    revs = selection.review_questions(conn, cert, "any_wrong")
    r = attempts.create_attempt(conn, revs, kind="review")
    assert conn.execute("SELECT kind, exam_id FROM attempt WHERE id=?", (r,)).fetchone()[:] == ("review", None)
    assert [x["id"] for x in attempts.attempt_questions(conn, r)] == [wrong]
    assert attempts.in_progress_attempts(conn)[0]["kind"] == "review"


def _section_id(conn, name_part):
    return conn.execute("SELECT id FROM section WHERE name LIKE ?", (f"%{name_part}%",)).fetchone()[0]


def test_drill_only_picks_from_section_across_exams(conn):
    cert, sec = _cert(conn), _section_id(conn, "Safety")
    pool = selection.section_pool(conn, cert, sec)
    assert len(pool) > 100
    revs = selection.drill_questions(conn, cert, sec, 30, rng=random.Random(0))
    assert len(revs) == 30 and len(set(revs)) == 30
    sections = {conn.execute("SELECT section_id FROM question_revision WHERE id=?", (r,)).fetchone()[0] for r in revs}
    assert sections == {sec}
    exams = {conn.execute("SELECT q.exam_id FROM question_revision r JOIN question q ON q.id=r.question_id WHERE r.id=?", (r,)).fetchone()[0] for r in revs}
    assert len(exams) > 1


def test_drill_priority_unseen_then_wrong_then_rest(conn):
    cert, sec = _cert(conn), _section_id(conn, "Safety")
    pool = selection.section_pool(conn, cert, sec)
    pool_revs = [selection._latest_revision(conn, q) for q in pool]
    # responde todas as Questions da Section: duas erradas (a mais recente por último), o resto certo
    a = attempts.start_attempt(conn, EXAM)
    rows = attempts.attempt_questions(conn, a)
    in_sec = [r for r in rows if r["id"] in pool_revs]
    assert len(in_sec) >= 4
    ids = [r["id"] for r in in_sec]
    answered = set()
    for rid, right in [(ids[0], False), (ids[1], False), (ids[2], True)]:
        pos = next(r["position"] for r in rows if r["id"] == rid)
        _answer(conn, a, pos, right)
        answered.add(rid)
    attempts.finish_attempt(conn, a)

    n = len(pool_revs)
    revs = selection.drill_questions(conn, cert, sec, n, rng=random.Random(0))
    assert set(revs) == set(pool_revs)
    unseen_count = n - 3
    assert set(revs[:unseen_count]).isdisjoint(answered)
    assert revs[unseen_count:unseen_count + 2] == [ids[1], ids[0]]  # errada mais recente primeiro
    assert revs[-1] == ids[2]

    pure = selection.drill_questions(conn, cert, sec, n, pure_random=True, rng=random.Random(0))
    assert set(pure) == set(pool_revs)


def test_drill_by_topic_primary_vs_secondary(conn):
    cert = _cert(conn)
    topic = "Bedrock: Guardrails"
    primary = selection.topic_pool(conn, cert, topic)
    with_secondary = selection.topic_pool(conn, cert, topic, include_secondary=True)
    assert 0 < len(primary) < len(with_secondary)
    assert set(primary) <= set(with_secondary)
    assert topic in selection.topic_names(conn, cert)

    revs = selection.drill_questions_by_topic(conn, cert, topic, 15, rng=random.Random(0))
    assert len(revs) == 15
    for r in revs:
        t = conn.execute("SELECT topic FROM revision_topic WHERE question_revision_id=? AND is_primary=1", (r,)).fetchone()[0]
        assert t == topic
    wide = selection.drill_questions_by_topic(conn, cert, topic, len(with_secondary), include_secondary=True, rng=random.Random(0))
    assert len(wide) == len(with_secondary)
    assert selection.drill_questions_by_topic(conn, cert, "Não existe", 5) == []
