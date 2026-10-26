# Backend de banco configurável (SQLite local ou Turso)

Status: ready-for-agent
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
