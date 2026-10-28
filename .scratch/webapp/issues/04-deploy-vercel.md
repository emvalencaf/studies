# Publicar o front na Vercel

Status: claimed
Blocked by: 03
Type: task

Publicar `web/` na Vercel (Hobby) apontando para a API do Render, com o acesso protegido e o CORS fechado. Os passos são do usuário e estão no wizard `scripts/vercel-deploy-wizard.sh`.

- Projeto importado de `emvalencaf/studies` com **Root Directory `web`**, Framework Vite, `VITE_API_URL` = URL do Render (do `.env`: `RENDER_API_URL`).
- **Vercel Authentication com escopo "All Deployments".** O padrão (Standard Protection) deixa o domínio de produção público: [documentação](https://vercel.com/docs/deployment-protection#choose-which-urls-to-protect). "All Deployments" é grátis em todos os planos. O wizard confere com `curl` que a URL não responde 200 sem login.
- `CORS_ORIGINS` no Render com a URL da Vercel (com `https://`, sem barra final). O wizard confere o preflight.
- `web/vercel.json` reescreve tudo para `/index.html`, senão abrir `/dashboard` direto dá 404 (React Router).
- Teste no PC e no celular: login da Vercel, tela de boot, token, um Exam, Dashboard; "Adicionar à tela inicial".

Critério: o front abre só para o usuário logado na Vercel, fala com a API e funciona no celular. Depois, avaliar a issue 07 do deploy (layout no celular) para o front novo e o desligamento do Streamlit (ADR 0002).

## Progress (2026-10-28)

No ar em https://studies-sigma-six.vercel.app. Conferido: a Vercel Authentication com "All Deployments" protege `/` e `/dashboard` (302 para o login da Vercel); o Render aceita a origem (preflight e GET reais, com `Content-Type` e `Authorization`); o build com a mesma `VITE_API_URL`, servido nessa origem, abre o Dashboard com os dados reais.

Tropeços, para não repetir:
- Foi colada no wizard a URL do Render no lugar do domínio da Vercel, e o `CORS_ORIGINS` ficou com a origem errada. O wizard agora rejeita isso e exige `x-vercel-id` na checagem de proteção.
- O `web/vercel.json` só chegou ao GitHub depois do primeiro deploy.
- Um **bloqueador de anúncios** barrava `onrender.com`; confirmado em janela anônima.

Falta o usuário confirmar: Exam e Dashboard no PC logado, `/dashboard` com F5 (teste do `vercel.json`) e o celular (adicionar à tela inicial). Depois disso a issue vira `resolved`, e o que ficou ruim no celular vira a issue de layout mobile.
