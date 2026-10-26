# Backend de banco configurável (SQLite local ou Turso)

Status: resolved
Blocked by: 02

`db.connect` passa a escolher o backend por variáveis de ambiente / `st.secrets` (URL e token do Turso). Sem credenciais, continua SQLite local, e os testes seguem rodando assim. Ajustar `app.py`, `load.py` e `backup.py` conforme o teste da 02. `playwright` vira extra `scrape` no `pyproject.toml`.

Critério: `uv run pytest` passa; o app e o `load` funcionam nos dois backends.

## Notas do teste (issue 02)

- Linhas do `libsql` são `tuple`: criar um adaptador que dê acesso por nome (`row["coluna"]`) e por índice, usando `cursor.description`, para os ~105 acessos do código.
- Não há `row_factory` nem `sqlite3.Row`. O `connect` atual usa os dois; o backend Turso precisa da alternativa.
- `attempts.py` (criação do snapshot) precisa de consulta em lote (1–2 consultas por Question são ~30 s a 130–250 ms cada). O `load` também ganha com `executemany`.
- `pandas.read_sql_query` funciona com a conexão libsql; ignorar o `UserWarning` ou passar por um cursor.
- Dashboard: `st.cache_data` com TTL curto.
- `libsql` está em `[dependency-groups] dev`; mover para as dependências do app.
- `backup.py` usa `sqlite3.backup()`, que não existe no libsql: para o Turso, exportar com `iterdump`/consultas ou pelo CLI; tratar na issue 05.

## Answer

`db.connect` escolhe o backend: `STUDIES_DB` ou caminho explícito → SQLite; sem eles e com `TURSO_URL`/`TURSO_TOKEN` → Turso (`libsql`). `TursoConnection` + `Row` dão a superfície do sqlite3 que o app usa (acesso por nome, `cursor()`, `lastrowid`, pandas). `load_env()` lê o `.env` no `load`; o app copia `TURSO_*` de `st.secrets` para o ambiente. `playwright` virou extra `scrape` (e entra no grupo dev); `libsql` é dependência do app. 86 testes passam (6 novos em `tests/test_db.py`).

Medido contra o Turso real: criar Attempt de 75 Questions caiu de 11,9 s para 1,15 s com INSERT de várias linhas em `create_attempt`; `record_answer` ~0,6 s; `answers_df` ~1,1 s.

**Descoberta:** `executemany` no libsql remoto faz uma ida e volta por linha (975 linhas = 139 s). Em lotes grandes usar INSERT de várias linhas.

**Pendências para as próximas issues:**
- `load`/`normalize.py` fazem uma consulta por registro: contra o Turso é lento (minutos). Não bloqueia, porque o conteúdo novo é raro, mas vale otimizar se incomodar.
- A conexão remota fica em `st.cache_resource` e pode expirar com o app ocioso; verificar no deploy (issue 06) e, se falhar, reconectar e repetir.
- `backup.py` ainda usa `sqlite3.backup()` (issue 05).
