# Backend de banco configurável (SQLite local ou Turso)

Status: needs-triage
Blocked by: 02

`db.connect` passa a escolher o backend por variáveis de ambiente / `st.secrets` (URL e token do Turso). Sem credenciais, continua SQLite local, e os testes seguem rodando assim. Ajustar `app.py`, `load.py` e `backup.py` conforme o teste da 02. `playwright` vira extra `scrape` no `pyproject.toml`.

Critério: `uv run pytest` passa; o app e o `load` funcionam nos dois backends.
