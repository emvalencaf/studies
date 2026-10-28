# Free tiers: Vercel Hobby, Render Free, Turso Free

Consultado em 2026-10-28, nas páginas oficiais. Cada afirmação cita a página que a sustenta; o que não foi possível confirmar está em "Em aberto".

## Vercel Hobby (front React)

- Gratuito, mas **só para uso pessoal e não comercial**. [plans/hobby](https://vercel.com/docs/plans/hobby)
- Folga enorme para um site estático: 100 GB de Fast Data Transfer, 1.000.000 de CDN Requests, 100 deployments por dia, 200 projetos. [plans/hobby](https://vercel.com/docs/plans/hobby)
- **Vercel Authentication está disponível em todos os planos** e protege deployments de produção e preview: quem abre é redirecionado para o login da Vercel e só entra quem tem acesso ao projeto (o dono do time Hobby entra). Password Protection é paga (US$ 20 por mês, plano Pro). [vercel-authentication](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication), [plans/hobby](https://vercel.com/docs/plans/hobby)
- Hobby permite só **um usuário externo** por conta com acesso concedido. [vercel-authentication](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication)
- **Repositório privado funciona** quando pertence a uma conta pessoal do GitHub; o que Hobby não faz é implantar de repositório privado de uma *organização* GitHub. O repositório do projeto está em conta pessoal (`emvalencaf`). [git](https://vercel.com/docs/git#deploying-private-git-repositories)
- Cartão: a página do plano não exige.

## Render Free web service (API)

- **750 horas de instância por mês** por workspace, sem acumular. Um único serviço ligado o mês inteiro usa ~744 h, então cabe um serviço. Esgotando, os serviços Free são suspensos até o mês seguinte. [docs/free](https://render.com/docs/free)
- **Dorme após 15 minutos sem requisições; acordar leva cerca de 1 minuto.** [docs/free](https://render.com/docs/free)
- **512 MB de RAM e 0,1 CPU** na tabela de planos de compute. A mesma página tem um cabeçalho que diz 0,5 CPU; a tabela e uma resposta do suporte confirmam 0,1. [compute-plans](https://render.com/docs/compute-plans), [community](https://community.render.com/t/the-free-instance-type-e-g-512mb-ram-0-1-cpu/39044)
- Sem disco persistente (sistema de arquivos efêmero), uma única instância, sem acesso shell/SSH; pode ser reiniciado a qualquer momento. [docs/free](https://render.com/docs/free)
- Banda e minutos de build: contam contra uma cota mensal, mas **a página não informa os valores**. Sem forma de pagamento, estourar a banda suspende os serviços Free até o fim do mês (em vez de cobrar). [docs/free](https://render.com/docs/free)
- Domínio próprio e TLS gerenciado continuam disponíveis. [docs/free](https://render.com/docs/free)

## Turso Free (banco)

- 100 bancos, 5 GB de armazenamento, 500 milhões de linhas lidas por mês, 10 milhões de linhas escritas por mês, 3 GB de sync, restauração a um ponto no tempo de 1 dia. "Start free, no credit card required." [turso.tech/pricing](https://turso.tech/pricing)

## Consequências para o Studies

1. **Acesso do front: resolvido sem código** (Vercel Authentication). Mas isso protege só o front.
2. **A API no Render continua pública.** CORS não é segurança: qualquer um que descubra a URL pode chamá-la e ler o histórico. A API precisa exigir um token (ou validar um login) em cada requisição.
3. **Cold start oficial é ~1 minuto**, o dobro do que eu havia suposto (~30 s). A tela de boot do protótipo precisa de timeout de pelo menos 90 s e de mensagem honesta.
4. **0,1 CPU e 512 MB** são o risco técnico real: pandas + libsql + FastAPI cabem na RAM, mas as consultas do Dashboard (várias, mais latência de rede ao Turso) podem ficar lentas com 0,1 CPU. Precisa de medida (issue 01).
5. Os limites do Turso (500 M leituras, 5 GB) são muito maiores que o uso de uma pessoa estudando.

## Em aberto

- Se o cadastro do Render exige cartão: fontes conflitantes (um artigo do próprio Render diz que não; a página oficial de limites só trata da ausência de forma de pagamento). Confirmar na tela de cadastro.
- Cota de banda e de minutos de build do Free: não publicadas nas páginas consultadas.
- RAM real usada pela API com pandas, e tempo das consultas do Dashboard em 0,1 CPU: só medindo.
