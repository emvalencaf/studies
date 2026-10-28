# Spike: Vercel + Render grátis servem para o Studies?

Status: ready-for-agent
Blocked by: -
Type: research

ADR `docs/adr/0003-react-vercel-render-api.md` (proposed). O visual alvo é a variante C do protótipo, na branch `prototype/webapp`, arquivo `prototype/webapp-prototype.html`.

Limites das páginas oficiais já levantados em `research-free-tiers.md` (2026-10-28). Falta o que só se confirma na prática:

- Cadastro do Render: exige cartão? (fontes conflitantes; testar o cadastro de verdade.)
- Cold start medido: tempo do primeiro `GET /health` depois de dormir, com FastAPI + pandas + libsql instalados. A documentação diz ~1 minuto; se passar de ~90 s, voltar ao plano B (Cloud Run).
- RAM e tempo das consultas do Dashboard com 512 MB e 0,1 CPU contra o Turso.
- Autenticação da API: a Vercel Authentication protege só o front. Definir como a API exige um token (variável de ambiente no Render, guardado no React) e testar CORS entre os domínios do Vercel e do Render.

Critério: relatório curto com os números e decisão: seguir, ou trocar de hospedagem. Se seguir, ADR 0003 vira `accepted`.
