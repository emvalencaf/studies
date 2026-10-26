# Deploy: app acessível do celular com custo R$ 0

Vocabulário em `GLOSSARY.md`. Decisão de hospedagem e dados em `docs/adr/0002-oracle-vm-sqlite-source-of-truth.md`.

## Objetivo

Estudar (Estudar + Dashboard) de qualquer lugar, inclusive do celular, com o PC desligado e sem gastar nada.

## Decisões

- **Hospedagem:** VM Oracle Always Free. ARM A1 primeiro, AMD Micro com swap como fallback. Plano B se a Oracle falhar de vez: PaaS grátis com Turso (libSQL) no lugar do SQLite.
- **Acesso:** URL pública com HTTPS (subdomínio DuckDNS + Caddy/Let's Encrypt) e `st.login` do Google, liberado só para o e-mail do usuário. Plano B de acesso: Tailscale. No celular, "Adicionar à tela inicial" (PWA); sem app nativo e sem modo offline.
- **Dados:** a VM é a única fonte da verdade do `studies.db`. O banco local sobe uma vez e o app local deixa de ser usado para estudar. Scrape continua no PC; `raw/` e `certification.json` sobem por rsync e o `load` roda na VM.
- **Backup:** cron diário na VM roda `studies.backup` e envia ao Google Drive com `rclone`, mantendo os 10 mais recentes. O aviso na UI passa a olhar esse backup.
- **Código:** `git init`, repositório privado no GitHub; `data/` e `storage_state.json` fora do git. Deploy = `git pull` + restart do serviço systemd.
- **Mobile:** layout ajustado depois do deploy, como issues separadas.

## Riscos conhecidos

- Cota A1 free reduzida em 2026 e falta frequente de capacidade; confirmar na página oficial da Oracle.
- VM ociosa (CPU, rede e memória < 20% por 7 dias) pode ser recuperada; o backup no Drive cobre.
- Conteúdo da Udemy é de terceiros: repo privado, `raw/` fora do git, login obrigatório.
