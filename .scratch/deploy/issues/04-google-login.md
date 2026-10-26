# Login Google restrito ao e-mail do usuário

Status: ready-for-agent
Blocked by: 03

`st.login` (OIDC Google) com `redirect_uri` = `https://<subdominio>/oauth2callback`. O usuário cria o OAuth client no Google Cloud Console; segredos em `.streamlit/secrets.toml` na VM (fora do git). Em `app.py`, antes de qualquer página: se não logado, tela de login; se o e-mail não for o permitido (config), `st.logout` e erro. O e-mail permitido vem de config, não de código. Testes do gate com `st.user` simulado.

Critério: outro e-mail Google é barrado; o do usuário entra no desktop e no celular.
