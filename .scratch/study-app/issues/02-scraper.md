# Scraper Playwright com sessão salva

Status: resolved
Blocked by: 01

Script em `src/` que abre o browser, deixa o usuário fazer login manual na primeira vez e salva `storage_state.json`. Lê o `certification.json`, descobre os quiz_ids pelo currículo de cada Course (fallback: IDs do JSON), baixa cada Exam com a version atual e grava o JSON bruto em `raw/<course>/<quiz_id>.json`. Critério: re-executar gera os mesmos 13 arquivos com 75 Questions cada.

## Answer

`src/studies/scrape.py`: `uv run python -m studies.scrape login` (login manual numa janela, salva `storage_state.json` com permissão 600) e `uv run python -m studies.scrape run`. As chamadas à API saem de dentro da página (fetch com os cookies), porque a Udemy bloqueia requisições fora do browser com 403. Lógica pura e orquestração testadas com página falsa em `tests/test_scrape.py`. **Não testado contra a Udemy real**: o login e o `run` precisam da sua sessão.
