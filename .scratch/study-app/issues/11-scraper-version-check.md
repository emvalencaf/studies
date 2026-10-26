# Re-scrape incremental por version

Status: resolved
Blocked by: 02

O scraper compara o `version` de cada quiz no currículo com o `version` guardado em `certification.json` e só baixa os Exams que mudaram, atualizando título e versão no JSON. Depois do re-scrape, `studies.load` cria as novas Question revisions (ADR 0001). Critério: sem mudança na Udemy, nenhum arquivo em `raw/` é reescrito.

## Answer

Feito junto com a 02, em `scrape.plan_course`: baixa só quiz novo, com `version` diferente da registrada em `certification.json`, ou sem arquivo em `raw/`; `--force` baixa tudo. Download incompleto (contagem diferente do `count` da Udemy) não é gravado nem atualiza a versão. Segunda rodada sem mudança não reescreve nenhum arquivo (testado). Depois, `uv run python -m studies.load` cria as novas Question revisions.
