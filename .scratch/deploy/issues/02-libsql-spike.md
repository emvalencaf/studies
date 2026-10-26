# Teste do cliente libSQL contra o Turso

Status: ready-for-human
Blocked by: -

O usuário cria conta no Turso (sem cartão), um banco e um token. O agente testa o cliente `libsql` contra uma cópia do `studies.db`: `connect`, `row_factory`, `executescript` do schema, `executemany`, transações, `pandas.read_sql_query`, e mede a latência das consultas do Dashboard e de uma Answer gravada. Confirma na página oficial os limites do free tier.

Critério: relatório (compatível ou não, latência por tela) e decisão: seguir com Turso ou ajustar o plano.
