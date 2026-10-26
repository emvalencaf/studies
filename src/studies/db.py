import os
import sqlite3
import warnings
from pathlib import Path

DEFAULT_DB = Path("data/studies.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS certification (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS course (
    id INTEGER PRIMARY KEY,
    certification_id INTEGER NOT NULL REFERENCES certification(id),
    slug TEXT NOT NULL,
    udemy_course_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    UNIQUE (certification_id, slug)
);
CREATE TABLE IF NOT EXISTS exam (
    id INTEGER PRIMARY KEY,  -- quiz_id da Udemy
    course_id INTEGER NOT NULL REFERENCES course(id),
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    label TEXT,  -- nome curto editado à mão no certification.json; a UI prefere este ao title
    udemy_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS section (
    id INTEGER PRIMARY KEY,
    certification_id INTEGER NOT NULL REFERENCES certification(id),
    name TEXT NOT NULL,
    UNIQUE (certification_id, name)
);
CREATE TABLE IF NOT EXISTS question (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES course(id),
    exam_id INTEGER NOT NULL REFERENCES exam(id),
    udemy_id INTEGER NOT NULL,
    UNIQUE (course_id, udemy_id)
);
CREATE TABLE IF NOT EXISTS question_revision (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES question(id),
    content_hash TEXT NOT NULL,
    assessment_type TEXT NOT NULL,
    section_id INTEGER NOT NULL REFERENCES section(id),
    prompt_html TEXT NOT NULL,
    explanation_html TEXT NOT NULL,
    options_json TEXT NOT NULL,   -- lista de HTML, na ordem original (a, b, c...)
    correct_json TEXT NOT NULL,   -- lista de letras
    links_json TEXT NOT NULL,
    ai_reasoning TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE (question_id, content_hash)
);

-- Derivado dos links da explicação (ver topics.py); recalculado a cada load, fora do hash da revisão.
CREATE TABLE IF NOT EXISTS revision_topic (
    question_revision_id INTEGER NOT NULL REFERENCES question_revision(id),
    topic TEXT NOT NULL,
    links INTEGER NOT NULL,
    is_primary INTEGER NOT NULL,
    PRIMARY KEY (question_revision_id, topic)
);
CREATE TABLE IF NOT EXISTS attempt (
    id INTEGER PRIMARY KEY,
    exam_id INTEGER REFERENCES exam(id),  -- NULL em Review e Drill
    kind TEXT NOT NULL DEFAULT 'exam' CHECK (kind IN ('exam', 'review', 'drill')),
    mode TEXT NOT NULL DEFAULT 'practice' CHECK (mode IN ('practice', 'exam')),
    shuffle INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'in_progress' CHECK (state IN ('in_progress', 'finished', 'abandoned')),
    started_at TEXT NOT NULL,
    finished_at TEXT
);
-- Snapshot das Questions do Attempt: fixa a revisão vista e a permutação das opções.
CREATE TABLE IF NOT EXISTS attempt_question (
    attempt_id INTEGER NOT NULL REFERENCES attempt(id),
    position INTEGER NOT NULL,
    question_revision_id INTEGER NOT NULL REFERENCES question_revision(id),
    permutation_json TEXT,  -- NULL = ordem original
    PRIMARY KEY (attempt_id, position),
    UNIQUE (attempt_id, question_revision_id)
);
CREATE TABLE IF NOT EXISTS answer (
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER NOT NULL REFERENCES attempt(id),
    question_revision_id INTEGER NOT NULL REFERENCES question_revision(id),
    selected_json TEXT NOT NULL,  -- letras na ordem original, ex.: ["a","c"]
    is_correct INTEGER NOT NULL,
    confidence TEXT CHECK (confidence IN ('confident', 'educated_guess', 'guess')),
    reasoning TEXT,
    time_seconds REAL,
    answered_at TEXT NOT NULL,
    UNIQUE (attempt_id, question_revision_id)
);
"""


def load_env(path: Path | str = ".env") -> None:
    """Carrega KEY='valor' do .env para os.environ sem sobrescrever o que já está definido."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() and not key.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class Row:
    """Linha acessível por índice, fatia ou nome de coluna, como o sqlite3.Row.
    O cliente libsql devolve tuplas, então o backend Turso precisa disto."""

    __slots__ = ("_names", "_values")

    def __init__(self, names: tuple[str, ...], values: tuple):
        self._names, self._values = names, tuple(values)

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return self._values[self._names.index(key)]
            except ValueError:
                raise IndexError(f"No item with that key: {key!r}") from None
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __eq__(self, other):
        return self._values == (other._values if isinstance(other, Row) else other)

    def __hash__(self):
        return hash(self._values)

    def __repr__(self):
        return f"Row({dict(zip(self._names, self._values))})"

    def keys(self) -> list[str]:
        return list(self._names)


class _Cursor:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        self._raw.execute(sql, tuple(params))
        return self

    def _row(self, values):
        names = tuple(d[0] for d in self._raw.description or ())
        return Row(names, values)

    def fetchone(self):
        values = self._raw.fetchone()
        return None if values is None else self._row(values)

    def fetchall(self) -> list[Row]:
        return [self._row(v) for v in self._raw.fetchall()]

    def fetchmany(self, size: int = 1) -> list[Row]:
        return [self._row(v) for v in self._raw.fetchmany(size)]

    def __iter__(self):
        return iter(self.fetchall())

    def close(self) -> None:
        self._raw.close()

    @property
    def lastrowid(self):
        return self._raw.lastrowid

    @property
    def rowcount(self):
        return self._raw.rowcount

    @property
    def description(self):
        return self._raw.description


class TursoConnection:
    """Dá à conexão remota do libsql a superfície do sqlite3 que o app usa."""

    def __init__(self, raw):
        self._raw = raw

    def cursor(self) -> _Cursor:
        return _Cursor(self._raw.cursor())

    def execute(self, sql, params=()) -> _Cursor:
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq) -> _Cursor:
        cur = self.cursor()
        cur._raw.executemany(sql, [tuple(p) for p in seq])
        return cur

    def executescript(self, script: str) -> None:
        self._raw.executescript(script)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        pass  # a conexão remota não segura recursos locais


# O pandas avisa que só testa sqlite3 e SQLAlchemy; o libsql funciona com ele (ver issue 02).
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy connectable")


def backend(conn) -> str:
    return "turso" if isinstance(conn, TursoConnection) else "sqlite"


def connect(path: Path | str | None = None, **kwargs):
    """SQLite local quando há caminho (argumento ou STUDIES_DB) ou não há credenciais do Turso;
    Turso quando TURSO_URL e TURSO_TOKEN estão no ambiente."""
    path = path or os.environ.get("STUDIES_DB")
    if path is None and os.environ.get("TURSO_URL"):
        import libsql

        conn = TursoConnection(libsql.connect(os.environ["TURSO_URL"], auth_token=os.environ["TURSO_TOKEN"]))
    else:
        path = path or DEFAULT_DB
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, **kwargs)
        conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Bancos criados antes de uma coluna existir ganham a coluna sem perder dados."""
    exam_cols = {r[1] for r in conn.execute("PRAGMA table_info(exam)")}
    if "label" not in exam_cols:
        conn.execute("ALTER TABLE exam ADD COLUMN label TEXT")
        conn.commit()
