import sqlite3
from datetime import datetime, timedelta

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
