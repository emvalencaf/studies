# Migrar o histórico para o Turso

Status: resolved
Blocked by: 03

Fazer `studies.backup` local, criar o schema no Turso e copiar o conteúdo do `studies.db`. Conferir contagens (Attempts, Answers, Question revisions) contra o banco local. Documentar o fluxo de conteúdo novo (`scrape run` → `load` apontando para o Turso) e que o app local deixa de ser usado para estudar.

Critério: contagens idênticas e o Dashboard no Turso igual ao local.

## Notas (issue 03)

- Durante o teste da 03 já foram copiados para o Turso, com os mesmos ids (`INSERT OR IGNORE`): `certification`, `course`, `exam`, `section`, `question`, `question_revision` (975) e `revision_topic`. O Attempt de teste foi apagado; `attempt`, `attempt_question` e `answer` estão vazios.
- Falta copiar o histórico (`attempt`, `attempt_question`, `answer`) e conferir que `question_revision.ai_reasoning` e `last_seen_at` do Turso batem com o local (o `INSERT OR IGNORE` não atualiza linhas que já existiam).
- Usar INSERT de várias linhas em lotes; `executemany` é uma ida e volta por linha.

## Answer

Backup local antes: `data/backups/studies-20261026-205224.db`. Copiei do `data/studies.db` para o Turso o que faltava (1 Attempt, 5 `attempt_question`, 1 `answer`) e comparei as 10 tabelas linha a linha: todas idênticas (certification 1, course 3, exam 13, section 5, question 975, question_revision 975, revision_topic 1752, attempt 1, attempt_question 5, answer 1), sem linhas divergentes e com `PRAGMA foreign_key_check` vazio. `metrics.answers_df` e `attempt_scores` dão o mesmo resultado nos dois bancos.

O `data/studies.db` local fica como cópia anterior à migração. O README agora diz que o Turso é a fonte da verdade e que o `load` grava nele.
