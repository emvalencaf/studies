import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from studies.db import DEFAULT_DB, SCHEMA, backend, connect, load_env

BACKUP_DIR = Path("data/backups")
KEEP = 10
STALE_AFTER = timedelta(days=7)
REMOTE_STALE_AFTER = timedelta(days=3)  # o backup do Turso roda todo dia
PREFIX = "studies-"


def backup(db_path: Path | str = DEFAULT_DB, backup_dir: Path | str = BACKUP_DIR, keep: int = KEEP,
           now: datetime | None = None) -> Path:
    """Copia o banco com a API de backup do sqlite3 (consistente mesmo com o app aberto)
    e mantém só os `keep` backups mais recentes."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    dest = backup_dir / f"{PREFIX}{stamp}.db"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    _prune(backup_dir, keep)
    return dest


def last_backup_age(backup_dir: Path | str = BACKUP_DIR, now: datetime | None = None) -> timedelta | None:
    files = sorted(Path(backup_dir).glob(f"{PREFIX}*.db"))
    if not files:
        return None
    last = datetime.strptime(files[-1].stem.removeprefix(PREFIX), "%Y%m%d-%H%M%S")
    return (now or datetime.now()) - last


def is_stale(backup_dir: Path | str = BACKUP_DIR, now: datetime | None = None) -> bool:
    age = last_backup_age(backup_dir, now)
    return age is None or age > STALE_AFTER


def _prune(backup_dir: Path, keep: int) -> None:
    for old in sorted(backup_dir.glob(f"{PREFIX}*.db"), reverse=True)[keep:]:
        old.unlink()


def backup_remote(conn, backup_dir: Path | str = BACKUP_DIR, keep: int = KEEP, now: datetime | None = None) -> Path:
    """Exporta o banco remoto (Turso) para um arquivo SQLite local, tabela por tabela.
    O libsql remoto não tem a API de backup do sqlite3."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"{PREFIX}{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}.db"
    dst = sqlite3.connect(dest)
    try:
        dst.executescript(SCHEMA)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        for table in tables:
            rows = [tuple(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
            if rows:
                marks = ",".join("?" * len(rows[0]))
                dst.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({marks})", rows)
        dst.commit()
    finally:
        dst.close()
    _prune(backup_dir, keep)
    return dest


def record_backup(conn, destination: str = "drive", now: datetime | None = None) -> None:
    """Marca no próprio banco que um backup terminou, para o app avisar quando ficar velho."""
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    conn.execute("INSERT INTO backup_log (created_at, destination) VALUES (?, ?)", (stamp, destination))
    conn.commit()


def remote_backup_age(conn, now: datetime | None = None) -> timedelta | None:
    row = conn.execute("SELECT max(created_at) FROM backup_log").fetchone()
    if row is None or row[0] is None:
        return None
    return (now or datetime.now(timezone.utc)) - datetime.fromisoformat(row[0])


def is_remote_stale(conn, now: datetime | None = None) -> bool:
    age = remote_backup_age(conn, now)
    return age is None or age > REMOTE_STALE_AFTER


def main() -> None:
    """`backup` copia o banco (SQLite local ou Turso) para data/backups/;
    `backup record` marca no banco que o envio ao Drive terminou."""
    load_env()
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        record_backup(connect())
        return
    conn = connect()
    if backend(conn) == "turso":
        print(backup_remote(conn))
    else:
        conn.close()
        print(backup())


if __name__ == "__main__":
    main()
