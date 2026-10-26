# Backup diário para o Google Drive

Status: ready-for-agent
Blocked by: 05

Na VM: configurar `rclone` com Google Drive (o usuário autoriza uma vez), cron diário que roda `studies.backup` e envia o arquivo para uma pasta do Drive, retenção de 10. Ajustar o aviso da UI para considerar o backup mais recente. Testar a restauração a partir do arquivo do Drive.

Critério: backup aparece no Drive; restore testado numa cópia.
