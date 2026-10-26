# Questions são revisões imutáveis identificadas por hash

A Udemy pode editar uma Question (texto, opções, gabarito) entre scrapes. Em vez de sobrescrever (upsert), cada re-scrape com conteúdo diferente cria uma nova Question revision, identificada pelo hash do conteúdo normalizado, e cada Answer aponta para a revisão que o usuário viu. Assim o histórico de Attempts e as métricas de Consistency continuam verdadeiros depois de uma edição; o custo é um modelo de dados um pouco mais complexo e o AI Reasoning preso a uma revisão.
