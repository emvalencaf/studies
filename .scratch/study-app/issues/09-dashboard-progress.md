# Dashboard: progressão e melhor desempenho

Status: resolved
Blocked by: 04

Granularidades e janelas do spec, acerto por janela com média móvel e tendência, melhor Attempt por Exam e melhor janela. Inéditas separadas de repetições. Review e Drill fora da nota do Exam.

## Answer

`src/studies/metrics.py` (funções puras sobre pandas, testadas em `tests/test_metrics.py`) e `src/studies/dashboard.py` (página Dashboard, escolhida na sidebar do `app.py`). Filtros: Certification, janela (7 dias, 30 dias, todo o período, intervalo livre), tipos de Attempt, granularidade (geral, Course, Exam, Section, Question), bucket dia ou semana e média móvel. Progressão com Inéditas separadas de Repetições (calculado no histórico todo, antes da janela), tendência contra a janela anterior de mesmo tamanho, melhor Attempt por Exam e melhor dia ou semana (mínimo de 10 Answers). Nota só com Attempts de Exam finalizados; Review e Drill ficam fora.
