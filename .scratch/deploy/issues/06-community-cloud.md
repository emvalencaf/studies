# Deploy no Streamlit Community Cloud

Status: claimed
Blocked by: 01, 04

O usuário conecta o GitHub ao Community Cloud, faz o deploy do repo privado e cadastra os secrets do Turso. O app fica privado, com convite só para o e-mail do usuário; se o loop de redirecionamento aparecer, o plano B é app público com `st.login` do Google restrito ao e-mail. Documentar em `docs/deploy.md` (deploy, secrets, convite, atalho na tela inicial).

Critério: o app abre no celular logado como o usuário, e outro e-mail é barrado.

## Comments

O Streamlit só autorizou repositório público, então o repo `emvalencaf/studies` foi tornado público (varredura antes: sem token, URL do Turso, `data/`, `.env` ou `storage_state.json` no histórico). O app continua privado pelo convite em Share. Roteiro: `scripts/deploy-wizard.sh`.
