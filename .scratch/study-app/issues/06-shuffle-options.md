# Embaralhar opções por Attempt

Status: resolved
Blocked by: 04

Toggle ao iniciar o Attempt. Grava a permutação por Question, mostra as letras na ordem vista e traduz o gabarito. A revisão do Attempt mostra o que foi visto.

## Answer

Checkbox "Embaralhar opções" na tela inicial. `start_attempt(shuffle=True)` grava `permutation_json` por Question (índice original da opção exibida em cada posição). A tela mostra letras a, b, c na ordem vista; `to_original`/`to_display` em `attempts.py` traduzem para as letras originais, que é o que fica em `answer.selected_json` e é comparado ao gabarito. Testado ida e volta.
