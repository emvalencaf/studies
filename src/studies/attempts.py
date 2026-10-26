import json
import random
import sqlite3
from datetime import datetime, timezone

CONFIDENCES = ("confident", "educated_guess", "guess")
LETTERS = "abcdefghij"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_revisions(conn: sqlite3.Connection, exam_id: int) -> list[int]:
    """Id da revisão mais recente de cada Question do Exam, na ordem original."""
    rows = conn.execute(
        """
        SELECT (SELECT r.id FROM question_revision r WHERE r.question_id = q.id
                ORDER BY r.last_seen_at DESC, r.id DESC LIMIT 1)
        FROM question q WHERE q.exam_id = ? ORDER BY q.id
        """,
        (exam_id,),
    ).fetchall()
    return [r[0] for r in rows]


def create_attempt(
    conn: sqlite3.Connection,
    revision_ids: list[int],
    kind: str = "exam",
    mode: str = "practice",
    shuffle: bool = False,
    exam_id: int | None = None,
    rng: random.Random | None = None,
) -> int:
    """Cria o Attempt com o snapshot das revisões. Com shuffle, grava por Question a
    permutação das opções: permutation[i] é o índice original da opção exibida na posição i."""
    rng = rng or random.Random()
    cur = conn.execute(
        "INSERT INTO attempt (exam_id, kind, mode, shuffle, started_at) VALUES (?, ?, ?, ?, ?)",
        (exam_id, kind, mode, int(shuffle), _now()),
    )
    attempt_id = cur.lastrowid
    option_counts: dict[int, int] = {}
    if shuffle:  # uma consulta por lote, não por Question: no Turso cada ida e volta custa ~200 ms
        for i in range(0, len(revision_ids), 500):
            chunk = revision_ids[i:i + 500]
            rows = conn.execute(
                f"SELECT id, options_json FROM question_revision WHERE id IN ({','.join('?' * len(chunk))})", chunk
            ).fetchall()
            option_counts.update({r[0]: len(json.loads(r[1])) for r in rows})
    snapshot = []
    for position, rev_id in enumerate(revision_ids, start=1):
        permutation = None
        if shuffle:
            order = list(range(option_counts[rev_id]))
            rng.shuffle(order)
            permutation = json.dumps(order)
        snapshot.append((attempt_id, position, rev_id, permutation))
    # INSERT de várias linhas: no Turso o executemany faz uma ida e volta por linha.
    for i in range(0, len(snapshot), 200):
        chunk = snapshot[i:i + 200]
        conn.execute(
            "INSERT INTO attempt_question (attempt_id, position, question_revision_id, permutation_json) VALUES "
            + ",".join(["(?, ?, ?, ?)"] * len(chunk)),
            [v for row in chunk for v in row],
        )
    conn.commit()
    return attempt_id


def start_attempt(
    conn: sqlite3.Connection,
    exam_id: int,
    mode: str = "practice",
    shuffle: bool = False,
    rng: random.Random | None = None,
) -> int:
    return create_attempt(conn, latest_revisions(conn, exam_id), "exam", mode, shuffle, exam_id, rng)


def to_original(display_letters: list[str], permutation: list[int] | None) -> list[str]:
    """Letras vistas na tela -> letras na ordem original da Udemy (a gravada e comparada ao gabarito)."""
    if permutation is None:
        return sorted(display_letters)
    return sorted(LETTERS[permutation[LETTERS.index(l)]] for l in display_letters)


def to_display(original_letters: list[str], permutation: list[int] | None) -> list[str]:
    if permutation is None:
        return sorted(original_letters)
    return sorted(LETTERS[permutation.index(LETTERS.index(l))] for l in original_letters)


def record_answer(
    conn: sqlite3.Connection,
    attempt_id: int,
    question_revision_id: int,
    selected: list[str],
    confidence: str | None = None,
    reasoning: str | None = None,
    time_seconds: float | None = None,
) -> bool:
    """Grava a Answer na hora. Retorna se está correta. Uma Answer por Question no Attempt."""
    if confidence is not None and confidence not in CONFIDENCES:
        raise ValueError(f"Confidence inválida: {confidence!r}")
    if not selected:
        raise ValueError("Answer sem opção selecionada")
    state, mode = conn.execute("SELECT state, mode FROM attempt WHERE id = ?", (attempt_id,)).fetchone()
    if state != "in_progress":
        raise ValueError("Attempt não está em andamento")
    correct = json.loads(
        conn.execute("SELECT correct_json FROM question_revision WHERE id = ?", (question_revision_id,)).fetchone()[0]
    )
    is_correct = set(selected) == set(correct)
    # Exam mode permite trocar a resposta antes de finalizar; Practice trava na primeira.
    on_conflict = (
        " ON CONFLICT (attempt_id, question_revision_id) DO UPDATE SET selected_json=excluded.selected_json, "
        "is_correct=excluded.is_correct, confidence=excluded.confidence, reasoning=excluded.reasoning, "
        "time_seconds=excluded.time_seconds, answered_at=excluded.answered_at"
        if mode == "exam" else ""
    )
    conn.execute(
        "INSERT INTO answer (attempt_id, question_revision_id, selected_json, is_correct, confidence, "
        "reasoning, time_seconds, answered_at) VALUES (?,?,?,?,?,?,?,?)" + on_conflict,
        (attempt_id, question_revision_id, json.dumps(sorted(selected)), int(is_correct),
         confidence, (reasoning or "").strip() or None, time_seconds, _now()),
    )
    conn.commit()
    return is_correct


def set_ai_reasoning(conn: sqlite3.Connection, question_revision_id: int, text: str) -> None:
    conn.execute(
        "UPDATE question_revision SET ai_reasoning = ? WHERE id = ?",
        (text.strip() or None, question_revision_id),
    )
    conn.commit()


def finish_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    conn.execute("UPDATE attempt SET state='finished', finished_at=? WHERE id=?", (_now(), attempt_id))
    conn.commit()


def abandon_attempt(conn: sqlite3.Connection, attempt_id: int) -> None:
    conn.execute("UPDATE attempt SET state='abandoned', finished_at=? WHERE id=?", (_now(), attempt_id))
    conn.commit()


def attempt_questions(conn: sqlite3.Connection, attempt_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT aq.position, aq.permutation_json, r.*, a.selected_json, a.is_correct, a.confidence, a.reasoning
        FROM attempt_question aq
        JOIN question_revision r ON r.id = aq.question_revision_id
        LEFT JOIN answer a ON a.attempt_id = aq.attempt_id AND a.question_revision_id = r.id
        WHERE aq.attempt_id = ? ORDER BY aq.position
        """,
        (attempt_id,),
    ).fetchall()


def first_unanswered(conn: sqlite3.Connection, attempt_id: int) -> int | None:
    rows = attempt_questions(conn, attempt_id)
    return next((r["position"] for r in rows if r["selected_json"] is None), None)


def summary(conn: sqlite3.Connection, attempt_id: int) -> dict[str, int]:
    rows = attempt_questions(conn, attempt_id)
    answered = [r for r in rows if r["selected_json"] is not None]
    correct = sum(r["is_correct"] for r in answered)
    return {
        "total": len(rows),
        "correct": correct,
        "wrong": len(answered) - correct,
        "skipped": len(rows) - len(answered),
    }


def in_progress_attempts(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT at.*, COALESCE(e.label, e.title) AS exam_title, at.kind AS kind, c.slug AS course_slug,
               (SELECT count(*) FROM answer WHERE attempt_id = at.id) AS answered,
               (SELECT count(*) FROM attempt_question WHERE attempt_id = at.id) AS total
        FROM attempt at LEFT JOIN exam e ON e.id = at.exam_id LEFT JOIN course c ON c.id = e.course_id
        WHERE at.state = 'in_progress' ORDER BY at.started_at DESC
        """
    ).fetchall()
