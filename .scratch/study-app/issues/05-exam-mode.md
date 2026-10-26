# Exam mode

Status: resolved
Blocked by: 04

Segunda opção de modo ao iniciar o Attempt: gabarito só ao finalizar. Tela final com nota, puladas e revisão. O modo fica gravado no Attempt.

## Answer

Modo escolhido ao iniciar (radio na tela inicial). No Exam mode a Answer é gravada na hora mas sem gabarito; dá para trocar a resposta até finalizar (upsert em `record_answer`, só nesse modo). Ao finalizar, ou em Attempts abandonados, o gabarito e a explicação aparecem para todas as Questions, inclusive as sem resposta. Testes em `tests/test_attempts.py` e `tests/test_app.py`.
