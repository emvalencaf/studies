# Backup do Turso para o Google Drive

Status: claimed
Blocked by: 04

Exportar o banco do Turso e enviar para uma pasta do Drive, mantendo os 10 mais recentes. O aviso da UI passa a considerar o backup mais recente. Roda como GitHub Actions agendado (diário), com o token do Turso e a credencial do Drive como secrets do repo privado. Testar a restauração em um banco de teste.

Critério: backup aparece no Drive; restore testado.

## Comments

Feito (commit `3488879`): `backup.backup_remote` exporta o Turso para um SQLite local (testado: 975 revisões, 1752 topics, integrity_check ok, ~10 s), tabela `backup_log` + `record_backup`, aviso no app lendo o último registro (alerta após 3 dias), `.github/workflows/backup.yml` (diário, 07:00 UTC, mantém 10 no Drive). Testes em `tests/test_backup.py`.

Falta a parte humana: `scripts/drive-backup-wizard.sh` (instala rclone sem sudo, autoriza o Drive com escopo `drive.file`, cadastra os secrets `TURSO_URL`, `TURSO_TOKEN`, `RCLONE_CONFIG` e dispara o primeiro backup). Depois, testar a restauração.

Riscos: o GitHub desativa workflows agendados em repo público sem atividade por 60 dias; o aviso do app (sem backup há mais de 3 dias) é o alarme. O token OAuth do Drive fica nos secrets.
