# Migrar o histórico para o Turso

Status: ready-for-agent
Blocked by: 03

Fazer `studies.backup` local, criar o schema no Turso e copiar o conteúdo do `studies.db`. Conferir contagens (Attempts, Answers, Question revisions) contra o banco local. Documentar o fluxo de conteúdo novo (`scrape run` → `load` apontando para o Turso) e que o app local deixa de ser usado para estudar.

Critério: contagens idênticas e o Dashboard no Turso igual ao local.

## Notas (issue 03)

- Durante o teste da 03 já foram copiados para o Turso, com os mesmos ids (`INSERT OR IGNORE`): `certification`, `course`, `exam`, `section`, `question`, `question_revision` (975) e `revision_topic`. O Attempt de teste foi apagado; `attempt`, `attempt_question` e `answer` estão vazios.
- Falta copiar o histórico (`attempt`, `attempt_question`, `answer`) e conferir que `question_revision.ai_reasoning` e `last_seen_at` do Turso batem com o local (o `INSERT OR IGNORE` não atualiza linhas que já existiam).
- Usar INSERT de várias linhas em lotes; `executemany` é uma ida e volta por linha.
