# Migração do banco e do conteúdo para a VM

Status: ready-for-agent
Blocked by: 03

Antes: `studies.backup` local. Enviar `data/studies.db` e `data/certifications/` para a VM por rsync, rodar `load` para validar e conferir contagens (Attempts, Answers, Questions) contra o banco local. Documentar em `docs/deploy.md` o fluxo de conteúdo novo (`scrape run` no PC → rsync → `load` na VM) e que o app local deixa de ser usado para estudar.

Critério: contagens idênticas e o histórico do Dashboard na VM igual ao local.
