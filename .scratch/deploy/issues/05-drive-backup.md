# Backup do Turso para o Google Drive

Status: needs-triage
Blocked by: 04

Exportar o banco do Turso e enviar para uma pasta do Drive, mantendo os 10 mais recentes. O aviso da UI passa a considerar o backup mais recente. Roda como GitHub Actions agendado (diário), com o token do Turso e a credencial do Drive como secrets do repo privado. Testar a restauração em um banco de teste.

Critério: backup aparece no Drive; restore testado.
