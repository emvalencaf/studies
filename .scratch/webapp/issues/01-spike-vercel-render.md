# Spike: Vercel + Render grátis servem para o Studies?

Status: resolved
Blocked by: -
Type: research

ADR `docs/adr/0003-react-vercel-render-api.md` (proposed). O visual alvo é a variante C do protótipo, na branch `prototype/webapp`, arquivo `prototype/webapp-prototype.html`.

Limites das páginas oficiais já levantados em `research-free-tiers.md` (2026-10-28). Falta o que só se confirma na prática:

- Cadastro do Render: exige cartão? (fontes conflitantes; testar o cadastro de verdade.)
- Cold start medido: tempo do primeiro `GET /health` depois de dormir, com FastAPI + pandas + libsql instalados. A documentação diz ~1 minuto; se passar de ~90 s, voltar ao plano B (Cloud Run).
- RAM e tempo das consultas do Dashboard com 512 MB e 0,1 CPU contra o Turso. Medida local já feita na issue 02 (~0,17 s de CPU, ~160 MB); falta medir no Render de verdade.
- Autenticação da API: a Vercel Authentication protege só o front. Definir como a API exige um token (variável de ambiente no Render, guardado no React) e testar CORS entre os domínios do Vercel e do Render.

Critério: relatório curto com os números e decisão: seguir, ou trocar de hospedagem. Se seguir, ADR 0003 vira `accepted`.

## Answer

Decisão: **seguir com Vercel + Render**; ADR 0003 passa a `accepted`. Medido pelo wizard `scripts/render-vercel-wizard.sh` em 2026-10-28, contra o serviço real (Render Free, região Oregon, banco no Turso em sa-east-1).

| Pergunta | Resultado |
|---|---|
| Render pediu cartão? | **Não** (relato do usuário no cadastro). |
| Vercel pediu cartão? | **Não.** O repositório privado `studies` aparece na importação. |
| Cold start (1ª chamada após 16 min parado) | **32 s**, abaixo do ~1 min da documentação. Uma única amostra. |
| `/health` com o serviço já acordado | 5 s no total, com tentativas do primeiro boot (não é cold start). |
| Dashboard acordado, de ponta a ponta | **1,27 s** (última de 3 chamadas), dentro da estimativa de 2 a 3 s. Inclui o trajeto PC → Oregon → Turso em sa-east-1. |
| Autenticação | `/certifications` sem token dá 401, com token dá 200 (o wizard confere antes de seguir). |

Fica para depois, porque dependem do front publicado: confirmar a Vercel Authentication no projeto real e definir `CORS_ORIGINS` no Render com a URL da Vercel. Vale repetir a medição do cold start algumas vezes: 32 s é uma amostra só, e o redeploy do push de 28/10 pode ter reiniciado o serviço.
