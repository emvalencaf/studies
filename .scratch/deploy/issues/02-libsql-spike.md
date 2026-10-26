# Teste do cliente libSQL contra o Turso

Status: resolved
Blocked by: -

O usuário cria conta no Turso (sem cartão), um banco e um token. O agente testa o cliente `libsql` contra uma cópia do `studies.db`: `connect`, `row_factory`, `executescript` do schema, `executemany`, transações, `pandas.read_sql_query`, e mede a latência das consultas do Dashboard e de uma Answer gravada. Confirma na página oficial os limites do free tier.

Critério: relatório (compatível ou não, latência por tela) e decisão: seguir com Turso ou ajustar o plano.

## Answer

Cliente `libsql==0.1.11` (adicionado como dependência de dev) contra o Turso, banco no AWS sa-east-1 (IP 18.228.87.104, ~80 ms de TCP a partir do WSL). Tudo abaixo foi medido do PC; do Community Cloud (provavelmente EUA) a latência tende a ser maior.

**Funciona:** `connect(url, auth_token=...)`, `executescript` do schema inteiro, `PRAGMA table_info`, `execute` com `?`, `executemany`, `commit`, `rollback` (descarta o que não foi commitado), `lastrowid`, `description`, `pandas.read_sql_query` (com `UserWarning` de que só sqlite3 e SQLAlchemy são testados; o resultado veio certo).

**Não funciona igual ao sqlite3:**
- Não existe `libsql.Row` nem `row_factory`: as linhas voltam como `tuple`. O código tem ~105 acessos do tipo `row["coluna"]` em `app.py`, `attempts.py`, `selection.py`, `dashboard.py` e `normalize.py`, então a issue 03 precisa de um adaptador (cursor/linha que mapeie nomes via `description`).
- O schema `CREATE TABLE IF NOT EXISTS` já foi aplicado no banco do Turso (vazio, sem dados); a issue 04 só precisa copiar as linhas.

**Latência (conexão remota direta):** ~130–250 ms por consulta; `executescript` do schema ~0,5 s; conexão inicial ~0,4 s. Implicações: `attempts.py` faz 1–2 consultas por Question ao criar um Attempt, ou seja ~30 s para 65 Questions se ficar como está. Precisa de uma consulta em lote (`executemany` / `IN (...)`). O `load` (975 Questions, uma consulta por linha) levaria alguns minutos, o que é aceitável por ser raro, mas melhora com `executemany`. O Dashboard já lê tudo em poucas consultas grandes (`read_sql_query`); usar `st.cache_data` com TTL curto.

**Alternativa medida, embedded replica** (`connect(arquivo_local, sync_url=..., auth_token=...)`): leituras 0 ms depois do `sync()` inicial (3,4 s) e leitura imediata do que acabou de escrever, mas cada escrita com commit levou 1,7–2,5 s. No Community Cloud o arquivo local é efêmero, então teria que sincronizar a cada reinício. Ruim para gravar cada Answer.

**Decisão:** seguir com o Turso em conexão remota direta, com adaptador de linhas, consultas em lote em `attempts.py` e cache no Dashboard. Embedded replica fica descartada por ora (escrita lenta). Risco aceito: cada clique em Answer leva ~0,3–0,5 s no celular.
