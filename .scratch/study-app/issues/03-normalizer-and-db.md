# Normalizador e schema SQLite

Status: resolved
Blocked by: 01

Ler o JSON bruto e carregar no `data/studies.db`: Certification, Course, Exam, Section, Question e Question revision (hash do conteúdo normalizado, ADR 0001), com suporte a `multiple-choice` e `multi-select`. Aplicar a tabela `sections` do `certification.json`. Carga idempotente: repetir não duplica; conteúdo alterado cria nova revisão. Testes com `pytest` usando amostras dos 13 arquivos (contagens, hash estável, revisão nova).

## Answer

`src/studies/db.py` (schema), `normalize.py` (carga idempotente com revisões por hash) e `load.py` (`uv run python -m studies.load`). 5 testes em `tests/test_normalize.py`. Banco real carregado: 975 Questions, 13 Exams, 5 Sections.
