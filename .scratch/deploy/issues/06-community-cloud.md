# Deploy no Streamlit Community Cloud

Status: claimed
Blocked by: 01, 04

O usuário conecta o GitHub ao Community Cloud, faz o deploy do repo privado e cadastra os secrets do Turso. O app fica privado, com convite só para o e-mail do usuário; se o loop de redirecionamento aparecer, o plano B é app público com `st.login` do Google restrito ao e-mail. Documentar em `docs/deploy.md` (deploy, secrets, convite, atalho na tela inicial).

Critério: o app abre no celular logado como o usuário, e outro e-mail é barrado.

## Comments

O Streamlit só autorizou repositório público, então o repo `emvalencaf/studies` foi tornado público (varredura antes: sem token, URL do Turso, `data/`, `.env` ou `storage_state.json` no histórico). O app continua privado pelo convite em Share. Roteiro: `scripts/deploy-wizard.sh`.

App no ar no Community Cloud. Primeiro bug em produção: depois de ~8 h ocioso, a conexão em cache expirou (`Hrana ... stream not found`) e todas as telas quebraram até um reboot. Correção: `TursoConnection` recebe uma função de conexão e se refaz sozinha ao ver esse erro, desde que não haja escrita pendente de commit (senão o erro sobe, para não perder dados em silêncio). Testado com falha simulada (3 testes novos); não consegui reproduzir a expiração real em testes de 2 min de ociosidade, então a confirmação final é o app aguentar uma noite parado.
