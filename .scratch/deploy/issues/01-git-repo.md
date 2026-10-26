# Repositório git privado

Status: ready-for-agent
Blocked by: -

`git init`; `.gitignore` acrescenta `data/` inteiro, `storage_state.json` e `.env`. Commit inicial com código, testes, docs e `.scratch/`. O usuário cria o repositório privado no GitHub e o agente configura o remote e dá o push.

Critério: `git ls-files` não lista nada de `data/` nem `storage_state.json`.
