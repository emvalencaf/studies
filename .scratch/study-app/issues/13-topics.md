# Topics a partir dos links da documentação

Status: resolved
Blocked by: 03, 08, 09

Estudo dirigido por tema, além das 5 Sections.

## Answer

`src/studies/topics.py` + `topics.json` (20 Topics, regras editáveis) + tabela `revision_topic` (principal e secundários, recalculada a cada `load`). Drill por Topic (com opção de incluir secundários), "Tema" como granularidade, aba Temas com mapa de arestas e vizinhos, Topics na tela da Question depois de responder. Cobertura real: 945 de 975 Questions (30 sem tema). Testes em `tests/test_topics.py`, `tests/test_selection.py` e `tests/test_metrics.py`. Decisões do usuário: separar "Amazon Q, Nova e outros", juntar Bedrock Agents com AgentCore, ver principal e arestas, regras em arquivo.
