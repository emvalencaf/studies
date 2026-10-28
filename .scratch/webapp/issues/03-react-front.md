# Front React (variante C) sobre a API

Status: resolved
Blocked by: 02
Type: task

Primeira versão do front em `web/` (Vite, React, TypeScript, Tailwind 3, Font Awesome, TanStack Query, React Router): tela de boot que espera `/health`, tela de token, Estudar (Attempts em andamento, novo Exam com modo e embaralhar), Attempt (mapa de questões, placar com meta de aprovação e botão para esconder, atalhos de teclado, Confiança e Raciocínio, gabarito e explicação conforme o modo) e Dashboard (prontidão, sequências, geral, nota por Exam, calibração, consistência, melhor Attempt por Exam).

## Answer

`web/` (README com como rodar). Testado no navegador contra a API local sobre uma cópia do banco: boot, token, Home com o Drill em andamento e 13 Exams, início de um Exam (meta 57/75), resposta com avanço automático, Dashboard com dados reais. `tsc` e `vitest` passam (3 testes do cliente da API).

- **Placar no Exam mode:** mostrar certas e erradas durante o Attempt revela, pelo total, se as respostas dadas estavam certas (o Streamlit fazia isso). Decisão: no Exam mode em andamento o placar nasce escondido; no Practice, visível; o botão alterna e a escolha fica salva por modo.
- **Fora desta issue:** Review e Drill na tela inicial (a API já suporta), janelas e granularidades do Dashboard, AI Reasoning, layout fino do celular, favicon/PWA, deploy na Vercel (depende do spike, issue 01).
