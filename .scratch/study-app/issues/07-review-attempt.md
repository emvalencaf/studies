# Review attempt com 4 filtros

Status: resolved
Blocked by: 04

Criar Attempt a partir de: erradas no último Attempt, erradas em qualquer Attempt, acertadas com chute, sem Confidence. Fica fora da nota do Exam.

## Answer

`src/studies/selection.py` (`review_questions`, `drill_questions`, `section_pool`) e `attempts.create_attempt` (generaliza `start_attempt`: kind, exam_id nulo). Tela inicial agora tem abas Exam completo, Review e Drill, com Certification, modo e embaralhar valendo para as três. "Último Attempt" = último Attempt finalizado da Certification com alguma Answer; em andamento e abandonados não contam. Review e Drill usam a revisão mais recente de cada Question. Testes em `tests/test_selection.py` e `tests/test_app.py`.
