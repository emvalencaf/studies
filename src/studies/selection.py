"""Escolha das Questions de Review e Drill. Devolve sempre ids da revisão mais recente."""
import random
import sqlite3

REVIEW_FILTERS = {
    "last_wrong": "Erradas no último Attempt",
    "any_wrong": "Erradas em qualquer Attempt",
    "lucky_guess": "Acertadas com chute",
    "no_confidence": "Respondidas sem Confidence",
}

_LATEST = """
(SELECT r.id FROM question_revision r WHERE r.question_id = {q}
 ORDER BY r.last_seen_at DESC, r.id DESC LIMIT 1)
"""


def _latest_revision(conn: sqlite3.Connection, question_id: int) -> int:
    return conn.execute("SELECT " + _LATEST.format(q="?"), (question_id,)).fetchone()[0]


def _answers(conn: sqlite3.Connection, certification_id: int):
    """Answers da Certification com a Question (não a revisão) a que se referem."""
    return conn.execute(
        """
        SELECT a.attempt_id, a.is_correct, a.confidence, a.answered_at, q.id AS question_id
        FROM answer a
        JOIN question_revision r ON r.id = a.question_revision_id
        JOIN question q ON q.id = r.question_id
        JOIN course c ON c.id = q.course_id
        WHERE c.certification_id = ?
        ORDER BY a.answered_at
        """,
        (certification_id,),
    ).fetchall()


def last_attempt_id(conn: sqlite3.Connection, certification_id: int) -> int | None:
    """Último Attempt finalizado da Certification com ao menos uma Answer."""
    row = conn.execute(
        """
        SELECT at.id FROM attempt at
        WHERE at.state = 'finished'
          AND EXISTS (SELECT 1 FROM answer a
                      JOIN question_revision r ON r.id = a.question_revision_id
                      JOIN question q ON q.id = r.question_id
                      JOIN course c ON c.id = q.course_id
                      WHERE a.attempt_id = at.id AND c.certification_id = ?)
        ORDER BY at.finished_at DESC, at.id DESC LIMIT 1
        """,
        (certification_id,),
    ).fetchone()
    return row[0] if row else None


def review_questions(conn: sqlite3.Connection, certification_id: int, filter_: str) -> list[int]:
    if filter_ not in REVIEW_FILTERS:
        raise ValueError(f"Filtro de Review desconhecido: {filter_!r}")
    answers = _answers(conn, certification_id)
    if filter_ == "last_wrong":
        last = last_attempt_id(conn, certification_id)
        picked = [a for a in answers if a["attempt_id"] == last and not a["is_correct"]]
    elif filter_ == "any_wrong":
        picked = [a for a in answers if not a["is_correct"]]
    elif filter_ == "lucky_guess":
        picked = [a for a in answers if a["is_correct"] and a["confidence"] == "guess"]
    else:
        picked = [a for a in answers if a["confidence"] is None]
    question_ids = sorted({a["question_id"] for a in picked})
    return [_latest_revision(conn, q) for q in question_ids]


def section_pool(conn: sqlite3.Connection, certification_id: int, section_id: int) -> list[int]:
    """Question ids da Certification cuja revisão mais recente está na Section."""
    rows = conn.execute(
        f"""
        SELECT q.id FROM question q JOIN course c ON c.id = q.course_id
        WHERE c.certification_id = ?
          AND (SELECT section_id FROM question_revision r WHERE r.id = {_LATEST.format(q="q.id")}) = ?
        ORDER BY q.id
        """,
        (certification_id, section_id),
    ).fetchall()
    return [r[0] for r in rows]


def topic_pool(conn: sqlite3.Connection, certification_id: int, topic: str, include_secondary: bool = False) -> list[int]:
    """Question ids da Certification cuja revisão mais recente tem o tema como principal
    (ou, com include_secondary, também os que só citam o tema)."""
    rows = conn.execute(
        f"""
        SELECT q.id FROM question q JOIN course c ON c.id = q.course_id
        WHERE c.certification_id = ?
          AND EXISTS (SELECT 1 FROM revision_topic t
                      WHERE t.question_revision_id = {_LATEST.format(q="q.id")}
                        AND t.topic = ? AND (t.is_primary = 1 OR ?))
        ORDER BY q.id
        """,
        (certification_id, topic, int(include_secondary)),
    ).fetchall()
    return [r[0] for r in rows]


def topic_names(conn: sqlite3.Connection, certification_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT t.topic FROM revision_topic t
        JOIN question_revision r ON r.id = t.question_revision_id
        JOIN question q ON q.id = r.question_id JOIN course c ON c.id = q.course_id
        WHERE c.certification_id = ? AND t.is_primary = 1
        GROUP BY t.topic ORDER BY count(*) DESC, t.topic
        """,
        (certification_id,),
    ).fetchall()
    return [r[0] for r in rows]


def drill_questions(
    conn: sqlite3.Connection,
    certification_id: int,
    section_id: int,
    n: int,
    pure_random: bool = False,
    rng: random.Random | None = None,
) -> list[int]:
    return prioritize(conn, certification_id, section_pool(conn, certification_id, section_id), n, pure_random, rng)


def drill_questions_by_topic(
    conn: sqlite3.Connection,
    certification_id: int,
    topic: str,
    n: int,
    pure_random: bool = False,
    include_secondary: bool = False,
    rng: random.Random | None = None,
) -> list[int]:
    pool = topic_pool(conn, certification_id, topic, include_secondary)
    return prioritize(conn, certification_id, pool, n, pure_random, rng)


def prioritize(
    conn: sqlite3.Connection,
    certification_id: int,
    pool: list[int],
    n: int,
    pure_random: bool = False,
    rng: random.Random | None = None,
) -> list[int]:
    """Inéditas primeiro, depois as de última Answer errada (a mais recente antes),
    depois o resto. Dentro de inéditas e do resto, ordem aleatória."""
    rng = rng or random.Random()
    pool = list(pool)
    if pure_random:
        rng.shuffle(pool)
        chosen = pool[:n]
    else:
        last = {}
        for a in _answers(conn, certification_id):  # ordenado por answered_at: a última vence
            last[a["question_id"]] = a
        unseen = [q for q in pool if q not in last]
        wrong = sorted((q for q in pool if q in last and not last[q]["is_correct"]),
                       key=lambda q: last[q]["answered_at"], reverse=True)
        rest = [q for q in pool if q in last and last[q]["is_correct"]]
        rng.shuffle(unseen)
        rng.shuffle(rest)
        chosen = (unseen + wrong + rest)[:n]
    return [_latest_revision(conn, q) for q in chosen]


def priority_questions(conn: sqlite3.Connection, certification_id: int, n: int = 20) -> list[int]:
    """Revisões das `n` Questions de maior risco (metrics.review_queue), na ordem do risco, mais arriscada primeiro."""
    from studies import metrics

    df = metrics.answers_df(conn, certification_id)
    queue = metrics.review_queue(df, metrics.consistency(df), top=n)
    return [_latest_revision(conn, q) for q in queue["question_id"]]
