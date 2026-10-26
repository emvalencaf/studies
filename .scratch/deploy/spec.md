# Deploy: app acessível do celular com custo R$ 0

Vocabulário em `GLOSSARY.md`. Decisão de hospedagem e dados em `docs/adr/0002-community-cloud-turso.md`. A VM Oracle foi tentada e descartada (cadastro recusado).

## Objetivo

Estudar (Estudar + Dashboard) de qualquer lugar, inclusive do celular, com o PC desligado e sem gastar nada.

## Decisões

- **App:** Streamlit Community Cloud, a partir do repositório privado no GitHub. Sem cartão.
- **Banco:** Turso (libSQL), no lugar do `studies.db` local. `db.connect` escolhe o backend: SQLite local por padrão (testes, uso offline) e Turso quando as credenciais estão no ambiente/secrets.
- **Acesso:** app privado do Community Cloud, com convite só para o e-mail do usuário. Plano B de acesso: app público com `st.login` do Google restrito ao e-mail. No celular, "Adicionar à tela inicial" (PWA); sem app nativo e sem offline.
- **Dados:** o Turso é a única fonte da verdade. O `studies.db` local sobe uma vez e o app local deixa de ser usado para estudar. Scrape e `load` rodam no PC e o `load` grava direto no Turso.
- **Dependências:** `playwright` sai das dependências do app (vira extra `scrape`), para o Community Cloud não instalar o que só o scraper usa.
- **Backup:** exportação do Turso para o Google Drive. GitHub Actions diário, com secrets no repo privado (issue 05).
- **Mobile:** layout ajustado depois do deploy, como issues separadas.

## Riscos conhecidos

- O cliente `libsql` pode não ser 100% compatível com `row_factory`, `executescript` e `pandas.read_sql_query`; a issue 02 é um teste antes de mexer no app.
- Latência de rede por consulta: o Dashboard roda várias; medir na issue 02.
- Limites dos free tiers (Turso, Community Cloud, 1 app privado) vêm de fontes de terceiros; confirmar nas páginas oficiais.
- Conteúdo da Udemy é de terceiros: repo privado, `data/` fora do git, app privado.
