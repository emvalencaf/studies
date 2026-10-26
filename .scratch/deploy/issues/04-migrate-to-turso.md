# Migrar o histórico para o Turso

Status: needs-triage
Blocked by: 03

Fazer `studies.backup` local, criar o schema no Turso e copiar o conteúdo do `studies.db`. Conferir contagens (Attempts, Answers, Question revisions) contra o banco local. Documentar o fluxo de conteúdo novo (`scrape run` → `load` apontando para o Turso) e que o app local deixa de ser usado para estudar.

Critério: contagens idênticas e o Dashboard no Turso igual ao local.
