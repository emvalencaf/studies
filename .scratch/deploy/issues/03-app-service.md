# App rodando na VM com HTTPS

Status: ready-for-agent
Blocked by: 01, 02

Na VM: instalar `uv`, clonar o repo, `uv sync` (sem Playwright), serviço systemd rodando `streamlit run src/studies/app.py` em localhost, Caddy como proxy com certificado Let's Encrypt, e subdomínio DuckDNS apontando para a VM. Documentar o passo a passo em `docs/deploy.md` (incluindo o deploy por `git pull` + restart).

Critério: a URL https abre o app (ainda sem login) e sobrevive a reboot da VM.
