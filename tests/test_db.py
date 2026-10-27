import json
import random
import sqlite3

import pandas as pd
import pytest

from studies import attempts
from studies.db import SCHEMA, Row, TursoConnection, backend, connect, load_env


@pytest.fixture
def turso_like():
    """TursoConnection sobre um sqlite3 puro: devolve tuplas, como o libsql."""
    c = TursoConnection(lambda r=sqlite3.connect(":memory:"): r)
    c.executescript(SCHEMA)
    return c


def test_row_by_name_index_and_slice():
    r = Row(("a", "b"), (1, "x"))
    assert (r["a"], r["b"], r[0], r[1]) == (1, "x", 0 + 1, "x")
    assert r[:] == (1, "x") and r == (1, "x") and r.keys() == ["a", "b"]
    assert dict(zip(r.keys(), r)) == {"a": 1, "b": "x"}
    with pytest.raises(IndexError):
        r["c"]


def test_cursor_returns_named_rows_and_lastrowid(turso_like):
    cur = turso_like.execute("INSERT INTO certification (slug, name) VALUES (?, ?)", ("s", "Nome"))
    turso_like.commit()
    assert cur.lastrowid == 1
    row = turso_like.execute("SELECT id, name FROM certification").fetchone()
    assert row["name"] == "Nome" and row[0] == 1
    assert [r["slug"] for r in turso_like.execute("SELECT * FROM certification")] == ["s"]
    assert turso_like.execute("SELECT * FROM certification WHERE id = 99").fetchone() is None


def test_pandas_reads_through_the_wrapper(turso_like):
    turso_like.executemany("INSERT INTO certification (slug, name) VALUES (?, ?)", [("a", "A"), ("b", "B")])
    turso_like.commit()
    df = pd.read_sql_query("SELECT slug, name FROM certification ORDER BY slug", turso_like)
    assert df.to_dict("records") == [{"slug": "a", "name": "A"}, {"slug": "b", "name": "B"}]


def test_create_attempt_batches_snapshot_with_shuffle(turso_like):
    turso_like.execute("INSERT INTO certification (id, slug, name) VALUES (1, 's', 'N')")
    turso_like.execute("INSERT INTO course VALUES (1, 1, 'c', 1, 'u')")
    turso_like.execute("INSERT INTO exam VALUES (1, 1, 1, 'E', NULL, 1)")
    turso_like.execute("INSERT INTO section VALUES (1, 1, 'S')")
    turso_like.execute("INSERT INTO question VALUES (1, 1, 1, 10), (2, 1, 1, 11)")
    for rev in (1, 2):
        turso_like.execute(
            "INSERT INTO question_revision (id, question_id, content_hash, assessment_type, section_id, prompt_html, "
            "explanation_html, options_json, correct_json, links_json, first_seen_at, last_seen_at) "
            "VALUES (?, ?, 'h', 'multiple-choice', 1, 'p', 'e', ?, '[\"a\"]', '[]', 't', 't')",
            (rev, rev, json.dumps(["x", "y", "z"][: rev + 1])),
        )
    turso_like.commit()
    a = attempts.start_attempt(turso_like, 1, shuffle=True, rng=random.Random(1))
    rows = attempts.attempt_questions(turso_like, a)
    assert [r["position"] for r in rows] == [1, 2]
    assert [len(json.loads(r["permutation_json"])) for r in rows] == [2, 3]


def test_connect_picks_backend_from_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("STUDIES_DB", raising=False)
    monkeypatch.delenv("TURSO_URL", raising=False)
    assert backend(connect(tmp_path / "x.db")) == "sqlite"
    monkeypatch.setenv("TURSO_URL", "libsql://nao-existe.example")
    monkeypatch.setenv("STUDIES_DB", str(tmp_path / "y.db"))
    assert backend(connect()) == "sqlite"  # STUDIES_DB vence as credenciais


def test_load_env_does_not_override_existing(monkeypatch, tmp_path):
    f = tmp_path / ".env"
    f.write_text("A_NEW='1'\nA_OLD='from file'\n# C=3\nbadline\n")
    monkeypatch.delenv("A_NEW", raising=False)
    monkeypatch.setenv("A_OLD", "from env")
    load_env(f)
    import os
    assert os.environ["A_NEW"] == "1" and os.environ["A_OLD"] == "from env"
    monkeypatch.delenv("A_NEW")


class _Flaky:
    """Conexão que perde o stream na primeira chamada de leitura, como o Turso após ficar ociosa."""

    def __init__(self, inner, fail_next=True):
        self.inner, self.fail_next = inner, fail_next

    def cursor(self):
        if self.fail_next:
            self.fail_next = False
            raise ValueError('Hrana: `api error: `status=404 Not Found, body={"error":"stream not found: x"}``')
        return self.inner.cursor()

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _flaky_conn(fail_next=True):
    shared = sqlite3.connect(":memory:")
    shared.executescript(SCHEMA)
    made = []

    def factory():
        made.append(1)
        return _Flaky(shared, fail_next=fail_next and len(made) == 1)

    return TursoConnection(factory), made


def test_reconnects_after_stream_lost_on_read():
    conn, made = _flaky_conn()
    assert conn.execute("SELECT count(*) FROM certification").fetchone()[0] == 0
    assert len(made) == 2  # conexão original + a refeita


def test_does_not_reconnect_with_pending_write():
    conn, made = _flaky_conn(fail_next=False)
    conn.execute("INSERT INTO certification (slug, name) VALUES ('a', 'A')")  # escrita sem commit
    conn._raw.fail_next = True
    with pytest.raises(ValueError, match="stream not found"):
        conn.execute("SELECT 1")
    assert len(made) == 1  # nada de reconectar: perderia a escrita pendente


def test_other_errors_are_not_swallowed():
    conn, made = _flaky_conn(fail_next=False)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT * FROM tabela_que_nao_existe")
    assert len(made) == 1
