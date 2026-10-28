---
status: accepted
---

# Front React no Vercel e API Python no Render, banco segue no Turso

Para sair do layout engessado do Streamlit, o front passa a ser um app React (visual da variante C do protótipo, na branch `prototype/webapp`) hospedado no Vercel, falando com uma API FastAPI no Render que reaproveita `metrics.py`, `attempts.py` e `selection.py` (pandas). O Turso e o backup no Drive ficam como estão (ADR 0002). Escolhidos por custo R$ 0 sem exigir cartão; o Streamlit no Community Cloud segue no ar até o React cobrir as duas páginas.

Alternativas descartadas: API no Cloud Run (exige cartão, e o cadastro da Oracle já foi recusado), API reescrita em TypeScript em Cloudflare Workers (perderia o pandas e o `metrics.py` teria que ser reescrito), Fly.io e Railway (hoje pedem cartão ou só dão crédito de teste).

Consequências (limites em `.scratch/webapp/research-free-tiers.md`, medidas no spike da issue 01): o Render Free dorme após 15 minutos sem uso; o cold start medido foi de ~32 s (a documentação diz ~1 min), com 512 MB de RAM e 0,1 CPU; o Dashboard acordado respondeu em ~1,3 s de ponta a ponta com a API em Oregon e o Turso em sa-east-1. O front mostra uma tela de boot enquanto `/health` não responde. Nenhum dos dois cadastros pediu cartão. O acesso ao front fica com a Vercel Authentication (grátis no Hobby, login da Vercel; o repositório pessoal privado é aceito), mas a API do Render é pública, então ela mesma exige um token em cada requisição, porque o conteúdo da Udemy é privado. Em aberto até o front ir ao ar: confirmar a Vercel Authentication no projeto real e fechar o `CORS_ORIGINS`.
