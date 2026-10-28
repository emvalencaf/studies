---
status: proposed
---

# Front React no Vercel e API Python no Render, banco segue no Turso

Para sair do layout engessado do Streamlit, o front passa a ser um app React (visual da variante C do protótipo, na branch `prototype/webapp`) hospedado no Vercel, falando com uma API FastAPI no Render que reaproveita `metrics.py`, `attempts.py` e `selection.py` (pandas). O Turso e o backup no Drive ficam como estão (ADR 0002). Escolhidos por custo R$ 0 sem exigir cartão; o Streamlit no Community Cloud segue no ar até o React cobrir as duas páginas.

Alternativas descartadas: API no Cloud Run (exige cartão, e o cadastro da Oracle já foi recusado), API reescrita em TypeScript em Cloudflare Workers (perderia o pandas e o `metrics.py` teria que ser reescrito), Fly.io e Railway (hoje pedem cartão ou só dão crédito de teste).

Consequências (limites conferidos nas páginas oficiais, em `.scratch/webapp/research-free-tiers.md`): o Render Free dorme após 15 minutos sem uso e acordar leva cerca de 1 minuto, com 512 MB de RAM e 0,1 CPU; o front mostra uma tela de boot enquanto `/health` não responde. O acesso ao front fica com a Vercel Authentication (grátis no Hobby, login da Vercel; o repositório pessoal privado é aceito), mas a API do Render é pública, então ela mesma precisa exigir um token em cada requisição, porque o conteúdo da Udemy é privado. Em aberto: se o cadastro do Render exige cartão, e se 0,1 CPU dá conta das consultas do Dashboard (issue 01). Esta ADR passa a `accepted` quando o spike medir isso.
