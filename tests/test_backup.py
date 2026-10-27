import sqlite3
from datetime import datetime, timedelta, timezone

from studies import backup
from studies.db import connect


def _db(tmp_path):
    path = tmp_path / "studies.db"
    conn = connect(path)
    conn.execute("INSERT INTO certification (slug, name) VALUES ('x', 'X')")
    conn.commit()
    conn.close()
    return path


def test_backup_copies_data_and_prunes_old(tmp_path):
    db, out = _db(tmp_path), tmp_path / "b"
    start = datetime(2026, 10, 1, 12)
    for i in range(12):
        backup.backup(db, out, keep=10, now=start + timedelta(days=i))
    files = sorted(out.glob("studies-*.db"))
    assert len(files) == 10
    assert files[0].name == "studies-20261003-120000.db"  # os 2 mais antigos saíram
    assert sqlite3.connect(files[-1]).execute("SELECT name FROM certification").fetchone()[0] == "X"


def test_backup_is_consistent_while_source_is_open(tmp_path):
    db = _db(tmp_path)
    live = connect(db)
    live.execute("INSERT INTO certification (slug, name) VALUES ('y', 'Y')")  # transação aberta, não commitada
    dest = backup.backup(db, tmp_path / "b")
    assert sqlite3.connect(dest).execute("SELECT count(*) FROM certification").fetchone()[0] == 1
    live.commit()


def test_staleness(tmp_path):
    out = tmp_path / "b"
    now = datetime(2026, 10, 20, 12)
    assert backup.is_stale(out, now) and backup.last_backup_age(out, now) is None
    backup.backup(_db(tmp_path), out, now=now - timedelta(days=3))
    assert not backup.is_stale(out, now)
    assert backup.is_stale(out, now + timedelta(days=5))


def _turso_like():
    from studies.db import SCHEMA, TursoConnection

    c = TursoConnection(sqlite3.connect(":memory:"))
    c.executescript(SCHEMA)
    c.execute("INSERT INTO certification (slug, name) VALUES ('x', 'X')")
    c.execute("INSERT INTO certification (slug, name) VALUES ('y', 'Y')")
    c.commit()
    return c


def test_backup_remote_exports_every_table_and_prunes(tmp_path):
    conn, out = _turso_like(), tmp_path / "b"
    start = datetime(2026, 10, 1, 12)
    for i in range(4):
        dest = backup.backup_remote(conn, out, keep=3, now=start + timedelta(days=i))
    assert len(list(out.glob("studies-*.db"))) == 3
    got = sqlite3.connect(dest)
    assert got.execute("SELECT slug FROM certification ORDER BY slug").fetchall() == [("x",), ("y",)]
    names = {r[0] for r in got.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"attempt", "answer", "question_revision", "backup_log"} <= names


def test_remote_backup_log_and_staleness(tmp_path):
    conn = connect(tmp_path / "x.db")
    now = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)
    assert backup.remote_backup_age(conn, now) is None and backup.is_remote_stale(conn, now)
    backup.record_backup(conn, now=now - timedelta(days=1))
    assert backup.remote_backup_age(conn, now) == timedelta(days=1)
    assert not backup.is_remote_stale(conn, now)
    backup.record_backup(conn, now=now - timedelta(days=5))  # o mais recente continua sendo o de 1 dia
    assert backup.remote_backup_age(conn, now) == timedelta(days=1)
    assert backup.is_remote_stale(conn, now + timedelta(days=3))
