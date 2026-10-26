# Projeto uv e estrutura de pastas

Status: resolved
Blocked by: -

Criar o projeto `uv` na raiz com Python 3.12 e as dependências do spec, `src/` como pacote, `.gitignore` para `storage_state.json`, `.env` e `data/studies.db`. Critério: `uv run pytest` e `uv run streamlit hello` funcionam.

## Answer

Pyproject, `src/studies`, `tests/` e `.gitignore` criados; `uv sync` e `uv run pytest` funcionam.
