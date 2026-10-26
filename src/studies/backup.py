import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from studies.db import DEFAULT_DB

BACKUP_DIR = Path("data/backups")
KEEP = 10
STALE_AFTER = timedelta(days=7)
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
    for old in sorted(backup_dir.glob(f"{PREFIX}*.db"), reverse=True)[keep:]:
        old.unlink()
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


def main() -> None:
    print(backup())


if __name__ == "__main__":
    main()
