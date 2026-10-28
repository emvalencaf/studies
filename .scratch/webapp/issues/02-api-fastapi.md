# API FastAPI sobre o código existente

Status: needs-triage
Blocked by: 01
Type: task

Extrair uma API HTTP de `metrics.py`, `attempts.py` e `selection.py`, sem mudar a lógica: `/health`, Attempts (criar, responder, finalizar), placar com `pass_progress`, dashboard (`readiness`, `streaks`, calibração, consistência). Reaproveita `db.connect` (Turso em produção, SQLite nos testes). `streamlit` e `plotly` ficam fora das dependências da API. Testes com `TestClient` sobre o banco SQLite de teste.

O front React (issue seguinte, depois do spike) consome essa API.
