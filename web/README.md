# Studies web (React)

Front do Studies (variante C do protótipo, branch `prototype/webapp`), falando com a API de `src/studies/api.py`. Decisão em `docs/adr/0003-react-vercel-render-api.md`.

## Rodar em dev

```
# API, num banco de teste (NÃO o data/studies.db com o seu histórico)
cp data/studies.db /tmp/dev.db
STUDIES_DB=/tmp/dev.db API_TOKEN=devtoken CORS_ORIGINS=http://localhost:5173 uv run uvicorn studies.api:app_from_env --factory --port 8000

# Front
cd web && cp .env.example .env.local && npm install && npm run dev
```

Abra http://localhost:5173 e cole `devtoken` na tela de token.

`npm run build` gera `dist/` (é o que a Vercel serve; `VITE_API_URL` aponta para a API do Render). `npm test` roda o Vitest.

## Pontos de atenção

- **Boot:** a tela espera `/health` até 2 min, porque o Render Free dorme (~1 min para acordar).
- **Token:** fica no `localStorage` deste navegador. Qualquer 401 da API o apaga e volta para a tela de token.
- **Placar:** mostra certas e erradas também no Exam mode (como o Streamlit fazia), então revela se as respostas já dadas estavam certas. O botão "placar" esconde, e a escolha fica salva.
