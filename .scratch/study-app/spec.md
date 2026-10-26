# Study app: simulados da Udemy com histórico de Attempts

Vocabulário em `GLOSSARY.md`. Decisão de dados em `docs/adr/0001-immutable-question-revisions.md`.

## Objetivo

Baixar os Exams dos Courses da Udemy de uma Certification, estudar numa UI Streamlit local e acompanhar a evolução com um dashboard. Cada vez que o usuário faz um Exam é um Attempt, guardado como snapshot.

## Dados

- Código em `src/`. Python 3.12, `uv`, `playwright`, `streamlit`, `pandas`, `plotly`, `sqlite3` sem ORM, `pytest` só para o normalizador.
- `data/certifications/<cert>/certification.json`: Courses, `quizzes` e a tabela `sections` (variantes de nome para as 5 Sections canônicas).
- `data/certifications/<cert>/raw/<course>/<quiz_id>.json`: payload bruto da Udemy, imutável. Já baixado para `aws-certified-gen-ai-developer` (13 Exams, 975 Questions).
- `data/studies.db`: SQLite normalizado, compartilhado entre Certifications.
- `storage_state.json` e `.env` ficam no `.gitignore`.

## Regras

- Question é única por `(Course, id da Udemy)`. Duplicatas entre Courses não são detectadas.
- Cada Question revision é imutável, identificada pelo hash do conteúdo normalizado. Re-scrape com conteúdo diferente cria nova revisão. O AI Reasoning fica na revisão.
- Tipos da Udemy: `multiple-choice` e `multi-select`. O Answer é um conjunto de letras. Outros tipos ficam fora da v1.
- Attempt: modo (Practice padrão, ou Exam), tipo (Exam completo, Review, Drill), estado (em andamento, finalizado, abandonado). Cada Answer é gravada na hora, com o tempo entre exibir e confirmar.
- Confidence, Reasoning e AI Reasoning são opcionais.
- Embaralhar as opções é um toggle ao iniciar o Attempt (desligado por padrão). A permutação fica gravada por Question e o gabarito é traduzido por ela.
- Review (filtros): erradas no último Attempt, erradas em qualquer Attempt, acertadas com chute, sem Confidence.
- Drill: uma Section, N Questions de todos os Exams da Certification. Prioriza inéditas e depois erradas mais recentemente. Toggle de sorteio puramente aleatório.
- Review e Drill ficam fora da nota do Exam.
- Questions puladas ficam fora do cálculo de acerto e aparecem como "puladas".

## Dashboard

- Granularidades: geral, Certification, Course, Exam, Section, Question.
- Janelas: 7 dias, 30 dias, todo o período, intervalo livre.
- Progressão: acerto por janela, média móvel, tendência contra a janela anterior. Inéditas separadas de repetições.
- Melhor desempenho: melhor Attempt por Exam e melhor janela na granularidade escolhida.
- Calibração por Confidence, com "sem marcação" à parte.
- Ritmo: Questions por dia e tempo médio por Question.
- Consistency por Question: estável (últimos 3 acertos seguidos, limiar configurável), instável, aprendida, poucos dados (menos de 3 Answers). Agregada por Section e Certification. Conta Answers de qualquer modo e ignora puladas.
- Mais erradas, e acertadas sem confiança.

## Fora da v1

Questions de lacunas ou arrastar, detecção de duplicatas, exportar relatórios, sincronizar entre máquinas, chamada de IA pelo app.

## Topics

Os Sections são 5 domínios largos. Cada Question ganha Topics derivados dos links da documentação AWS na explicação (`topics.json` por Certification, regras editáveis, recalculadas a cada `load` fora do hash da revisão). Principal = o mais citado; secundários e arestas (pares citados juntos) ficam visíveis. Drill e granularidade do dashboard usam o principal; o Drill pode incluir secundários. Topics só aparecem na tela depois da resposta.
