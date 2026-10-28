# API FastAPI sobre o código existente

Status: resolved
Blocked by: 01
Type: task

Extrair uma API HTTP de `metrics.py`, `attempts.py` e `selection.py`, sem mudar a lógica: `/health`, Attempts (criar, responder, finalizar), placar com `pass_progress`, dashboard (`readiness`, `streaks`, calibração, consistência). Reaproveita `db.connect` (Turso em produção, SQLite nos testes). `streamlit` e `plotly` ficam fora das dependências da API. Testes com `TestClient` sobre o banco SQLite de teste.

O front React (issue seguinte, depois do spike) consome essa API.

## Answer

`src/studies/api.py` (FastAPI), testada em `tests/test_api.py` (8 testes, `TestClient` sobre SQLite em memória). Rotas: `GET /health` (única sem token), `GET /certifications`, `GET /certifications/{id}/exams`, `GET|POST /attempts`, `GET /attempts/{id}` (placar com `pass_progress` e mapa de questões), `GET /attempts/{id}/questions/{pos}`, `POST /attempts/{id}/answers|finish|abandon`, `GET /dashboard/{cert_id}` (prontidão, sequências, acerto, notas por Exam, calibração, consistência). Review e Drill (por Section e por tema) saem de `POST /attempts` com `kind`.

- **Token:** toda rota exige `Authorization: Bearer <API_TOKEN>`; sem `API_TOKEN` a API recusa subir. CORS vem de `CORS_ORIGINS`. Subir com `uvicorn studies.api:app_from_env --factory` (extra `api` no `pyproject.toml`; `fastapi` e `httpx` no grupo dev).
- **Sem vazamento do gabarito:** gabarito, explicação e acerto só saem quando o modo permite (Practice depois de responder, ou Attempt encerrado). No Exam mode em andamento nem o mapa nem a resposta dizem se acertou. Coberto por teste.
- **Uma conexão, um lock:** a conexão (sqlite3 ou Turso) não é segura entre threads, então as rotas se serializam num lock. Basta para um usuário.
- **Fora desta issue:** janelas de tempo, granularidades, progressão, ritmo, grafo de temas e `AI Reasoning` do Dashboard (o Streamlit continua cobrindo), e o `load`/scrape.

### Medição para o spike (issue 01), do PC, SQLite local, 2.250 Answers em 30 Exams

- Dashboard: ~0,17 s de CPU por chamada. Em 0,1 CPU isso é ≥ ~1,7 s se for só CPU (estimativa, não medido no Render), mais ~2 idas ao Turso (`answers_df` e `attempt_scores`, ~0,2 s cada).
- Memória: pico de ~160 MB no processo de teste (incluindo a carga do banco), abaixo dos 512 MB. `streamlit` e `plotly` não são importados pela API.
- Responder uma Question: ~10 ms de CPU, mais a latência do Turso.

Falta no spike: cold start e cadastro reais no Render, e a latência real contra o Turso.
