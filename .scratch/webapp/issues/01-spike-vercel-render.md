# Spike: Vercel + Render grátis servem para o Studies?

Status: ready-for-agent
Blocked by: -
Type: research

ADR `docs/adr/0003-react-vercel-render-api.md` (proposed). O visual alvo é a variante C do protótipo, na branch `prototype/webapp`, arquivo `prototype/webapp-prototype.html`.

Confirmar nas páginas oficiais (Vercel, Render, Turso) e com um teste real:

- Limites dos free tiers: RAM e CPU do web service do Render, horas por mês, tempo para dormir, cartão exigido ou não; limites do Vercel Hobby, incluindo uso de repositório privado.
- Cold start medido: tempo do primeiro `GET /health` depois de dormir, com FastAPI + pandas + libsql instalados. Se passar de ~60 s, voltar ao plano B (Cloud Run).
- Acesso: o conteúdo da Udemy é privado. Descobrir o que o Vercel Hobby oferece de proteção e, se não houver, propor login simples na API (um token, ou Google restrito ao e-mail do usuário) e como o React o guarda.
- CORS entre o domínio do Vercel e o do Render.

Critério: relatório curto com os números e decisão: seguir, ou trocar de hospedagem. Se seguir, ADR 0003 vira `accepted`.
