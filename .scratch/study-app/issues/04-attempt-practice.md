# Attempt em Practice mode no Streamlit

Status: resolved
Blocked by: 03

UI para escolher um Exam e fazer um Attempt completo em Practice mode: opções na ordem original, Answer como conjunto de letras, gabarito e explicação da Udemy logo após cada Answer, Confidence, Reasoning e AI Reasoning opcionais (AI Reasoning grava na Question revision), tempo por Question. Cada Answer gravada na hora. Estados em andamento, finalizado, abandonado, com retomada.

## Answer

`src/studies/attempts.py` (regras: snapshot de revisões, Answer como conjunto, estados, retomada, AI Reasoning na revisão), `app.py` (Streamlit) e tabelas `attempt`, `attempt_question`, `answer`. Rodar: `uv run streamlit run src/studies/app.py`. Testes em `tests/test_attempts.py` e `tests/test_app.py` (fluxo completo via AppTest). Opções embaralhadas, Exam mode e Review/Drill ainda não (issues 05-08), mas o schema já tem `mode`, `kind`, `shuffle` e `permutation_json`.
