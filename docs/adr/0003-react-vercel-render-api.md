---
status: proposed
---

# Front React no Vercel e API Python no Render, banco segue no Turso

Para sair do layout engessado do Streamlit, o front passa a ser um app React (visual da variante C do protótipo, na branch `prototype/webapp`) hospedado no Vercel, falando com uma API FastAPI no Render que reaproveita `metrics.py`, `attempts.py` e `selection.py` (pandas). O Turso e o backup no Drive ficam como estão (ADR 0002). Escolhidos por custo R$ 0 sem exigir cartão; o Streamlit no Community Cloud segue no ar até o React cobrir as duas páginas.

Alternativas descartadas: API no Cloud Run (exige cartão, e o cadastro da Oracle já foi recusado), API reescrita em TypeScript em Cloudflare Workers (perderia o pandas e o `metrics.py` teria que ser reescrito), Fly.io e Railway (hoje pedem cartão ou só dão crédito de teste).

Consequências: o free tier do Render dorme sem uso, então a primeira abertura do dia tem cold start de dezenas de segundos; o front mostra uma tela de boot enquanto `/health` não responde. Em aberto: o Vercel não protege o front por senha no plano grátis (a confirmar) e o conteúdo da Udemy é privado, então o acesso precisa de login na API (decidir no spike, issue 01). Os limites dos free tiers vêm da memória do agente e ainda não foram conferidos nas páginas oficiais. Esta ADR passa a `accepted` quando o spike confirmar os limites e o acesso.
