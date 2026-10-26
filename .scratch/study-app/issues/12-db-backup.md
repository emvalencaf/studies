# Backup do studies.db

Status: resolved
Blocked by: 04

O banco guarda o histórico de Attempts, que não dá para regerar (o `raw/` dá). Comando `uv run python -m studies.backup` que copia `data/studies.db` para `data/backups/studies-<timestamp>.db` usando a API de backup do `sqlite3`, e mantém os 10 mais recentes. Avisar na UI se o último backup tem mais de 7 dias.

## Answer

`src/studies/backup.py`: `uv run python -m studies.backup` copia para `data/backups/studies-<timestamp>.db` com a API de backup do sqlite3 e mantém os 10 mais recentes. A tela Estudar avisa quando não há backup ou o último tem mais de 7 dias. Testado: poda, consistência com transação aberta e aviso de backup velho.
