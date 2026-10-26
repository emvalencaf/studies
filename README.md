# Studies

App local para praticar simulados de certificações (hoje, AWS Certified Generative AI Developer - Professional, AIP-C01) a partir dos cursos da Udemy em que você tem subscrição. Baixa os Exams, deixa você fazê-los numa UI Streamlit e guarda cada Attempt com Confidence e raciocínio, para um dashboard acompanhar sua evolução.

O vocabulário (Certification, Course, Exam, Question, Attempt, Answer, Drill, Review...) está em [`GLOSSARY.md`](GLOSSARY.md). A decisão sobre revisões de Questions está em [`docs/adr/`](docs/adr/).

## Requisitos

- Python 3.12 e [`uv`](https://docs.astral.sh/uv/)
- Só para o scraper: `uv sync --extra scrape` e `uv run playwright install chromium`

```bash
uv sync
```

**Banco:** SQLite local em `data/studies.db` por padrão. Com `TURSO_URL` e `TURSO_TOKEN` no `.env` (ou em `st.secrets`), o app e o `load` usam o Turso; `STUDIES_DB` força o SQLite local.

## Uso

### Estudar e acompanhar

```bash
uv run streamlit run src/studies/app.py
```

A sidebar tem duas páginas.

**Estudar**
- **Exam completo**, **Review** e **Drill por Section** são as três formas de iniciar um Attempt. Escolha a Certification, o modo e se quer embaralhar as opções.
- **Practice mode** (padrão) mostra o gabarito e a explicação logo após cada resposta. **Exam mode** só mostra ao finalizar e permite trocar a resposta até lá.
- **Review** refaz Questions por filtro: erradas no último Attempt, erradas em qualquer Attempt, acertadas com chute ou respondidas sem Confidence.
- **Drill** sorteia Questions de uma Section **ou de um Topic**, tirando de todos os Exams. Por padrão prioriza inéditas e depois as erradas mais recentemente; há um toggle para sorteio puramente aleatório. No Drill por Topic, o checkbox "incluir Questions que só citam o tema" traz também as que têm o Topic como secundário.
- Confidence (confiante, educated guess, chute), Reasoning e AI Reasoning são sempre opcionais. O AI Reasoning é um texto que você cola de uma IA externa (por exemplo, o Gemini no browser); ele fica na Question e vale para todos os Attempts.
- Cada resposta é gravada na hora. Um Attempt interrompido fica em andamento e é retomado pela tela inicial.

**Dashboard**
- Filtros: Certification, janela (7 dias, 30 dias, todo o período, intervalo livre), tipos de Attempt, granularidade (geral, Course, Exam, Section, Question), bucket (dia ou semana) e média móvel.
- Abas: Progressão (inéditas separadas de repetições), Melhor desempenho, Calibração por Confidence, Ritmo, Consistência, Temas e Questions (mais erradas e acertadas com chute).
- **Temas:** acerto por Topic principal, mapa de arestas (quantas Questions citam cada par de Topics) e, para um Topic escolhido, seus vizinhos com o acerto nas Questions em comum. "Tema" também é uma granularidade da aba Progressão.
- A nota de um Exam só considera Attempts de Exam finalizados. Review e Drill ficam de fora. Questions puladas não entram no acerto.

### Atualizar os Exams da Udemy

```bash
uv run python -m studies.scrape login     # uma vez: login manual numa janela, salva storage_state.json
uv run python -m studies.scrape run       # baixa só o que mudou
uv run python -m studies.load             # cria as novas Question revisions no banco
```

- O `run` compara o `version` de cada quiz no currículo com o do `certification.json`. Baixa quizzes novos, com versão diferente ou sem arquivo em `raw/`. `--force` baixa tudo.
- As chamadas à API saem de dentro da página, com os cookies do browser, porque a Udemy bloqueia requisições fora dele. Por isso a janela aparece; `--headless` existe, mas pode ser bloqueado.
- Se a sessão expirar, o `run` avisa para rodar o `login` de novo.
- Rodar `load` é seguro a qualquer momento: conteúdo igual não duplica nada, e conteúdo alterado cria uma nova Question revision. Attempts antigos continuam apontando para a revisão que você viu.

### Backup

```bash
uv run python -m studies.backup
```

Copia `data/studies.db` para `data/backups/studies-<data-hora>.db` e mantém os 10 mais recentes. A tela Estudar avisa quando não há backup ou o último tem mais de 7 dias. O `studies.db` guarda o seu histórico, que não dá para regerar; o `raw/` dá.

### Testes

```bash
uv run pytest
```

## Onde ficam os dados

```
data/
├── studies.db                                      # SQLite com Questions e Attempts (backup!)
├── backups/                                        # cópias do studies.db
└── certifications/
    └── aws-certified-gen-ai-developer/
        ├── certification.json                      # Courses, Exams e mapeamento de Sections
        ├── topics.json                             # regras que ligam URLs da documentação a Topics
        └── raw/<course>/<quiz_id>.json             # payload bruto da Udemy, não editar
```

`storage_state.json` e `.env` ficam na raiz e estão no `.gitignore`. O `storage_state.json` guarda os cookies da sua sessão na Udemy: trate como segredo.

### Topics (`topics.json`)

Os Sections do exame são só 5 domínios, largos demais para estudo dirigido. Por isso cada Question ganha Topics derivados dos links da documentação AWS que a explicação da Udemy cita (quase todas citam):

- Cada link vira uma chave `<serviço>/<resto do caminho>` (sem idioma, sem `latest`, sem `.html`). A **primeira regra** de `topics.json` cujo padrão casa define o Topic do link.
- O Topic **principal** da Question é o mais citado; empate vai para a regra que vem antes no arquivo. Os demais são **secundários**, e cada par de Topics citados juntos é uma **aresta**.
- Questions sem link reconhecido ficam em "Sem tema" (hoje, 30 de 975).
- Para reclassificar, edite as regras e rode `uv run python -m studies.load`. Os Topics não entram no hash da Question revision, então mudar regras não cria revisões novas.
- Os Topics aparecem na tela só depois que você responde, porque o nome do tema pode sugerir a resposta.

### `certification.json`

- `courses.<slug>`: `udemy_course_id`, `url` e a lista `quizzes` (`id`, `title`, `version` e `label` opcional).
- `label`: nome curto do Exam, editado à mão. A UI prefere o `label` ao título da Udemy, e o scraper nunca o sobrescreve.
- `sections`: mapeia cada nome de Section que aparece nos payloads (a Udemy trunca em ~60 caracteres e cada Course escreve de um jeito) para as 5 Sections canônicas. Uma Section sem mapeamento faz o `load` falhar de propósito.

### Adicionar outra Certification

1. Crie `data/certifications/<slug>/certification.json` com `name`, `courses` (cada um com `udemy_course_id`, `url` e `quizzes: []`) e `sections`.
2. Rode `scrape run data/certifications/<slug>`, depois `load data/certifications/<slug>`.
3. Se o `load` reclamar de Section sem mapeamento, acrescente as variantes em `sections` e rode de novo.
4. Opcional: crie um `topics.json` (copie o da AWS como ponto de partida) para ter Topics.

## Estrutura do código

| Arquivo | O que faz |
|---|---|
| `src/studies/app.py` | UI Streamlit (Estudar) e navegação |
| `src/studies/dashboard.py` | Página Dashboard e gráficos |
| `src/studies/attempts.py` | Regras de Attempt: snapshot, Answer, modos, embaralhar, retomada |
| `src/studies/selection.py` | Escolha das Questions de Review e Drill |
| `src/studies/metrics.py` | Métricas do dashboard (funções puras sobre pandas) |
| `src/studies/normalize.py` | Carga do JSON bruto no SQLite, com revisões por hash |
| `src/studies/topics.py` | Topics e arestas a partir dos links das explicações |
| `src/studies/db.py` | Schema, migrações leves e escolha do backend (SQLite local ou Turso) |
| `src/studies/scrape.py` | Login e download dos Exams |
| `src/studies/backup.py` | Backup do banco |

## Limites conhecidos

- Só `multiple-choice` e `multi-select`. Outros tipos de Question da Udemy são ignorados.
- Questions parecidas em Courses diferentes contam como Questions diferentes.
- Os dados da Udemy são conteúdo de terceiros, baixado com a sua subscrição para estudo pessoal. Pense nisso antes de versionar `data/certifications/*/raw/` ou compartilhar o repositório.
- O scraper depende da API interna da Udemy e pode quebrar se ela mudar.
