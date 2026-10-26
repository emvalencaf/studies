# Studies

Ferramenta pessoal para praticar simulados de certificações (inicialmente AWS) obtidos de cursos da Udemy, registrando cada tentativa com confiança e raciocínio para acompanhar a evolução.

## Language

**Certification**:
Uma certificação-alvo que o usuário está estudando (ex.: AWS Certified Generative AI Developer Pro). Agrupa um ou mais Courses de origem.
_Avoid_: Prova real, test

**Course**:
Um curso da Udemy que fornece Exams para uma Certification.
_Avoid_: Pack, curso de simulados

**Exam**:
Um simulado completo dentro de um Course (um *quiz* da Udemy), composto por Questions.
_Avoid_: Quiz, simulado, test

**Question**:
Uma questão de um Exam, identificada pelo `id` da Udemy, com opções e uma ou mais respostas corretas.
_Avoid_: Item, assessment

**Attempt**:
Uma execução, completa ou parcial, de um Exam pelo usuário. Depois de finalizado é imutável e funciona como o snapshot daquela vez.
_Avoid_: Snapshot, run, sessão

**Answer**:
A resposta do usuário a uma Question dentro de um Attempt: o conjunto de opções escolhidas.
_Avoid_: Resposta, response

**Section**:
O domínio de conteúdo ao qual uma Question pertence, conforme informado pela Udemy (ex.: "FM Integration, Data Management, and Compliance").
_Avoid_: Categoria, tópico, domínio

**Practice mode**:
Modo de Attempt em que o gabarito e a explicação aparecem logo após cada Answer. É o modo padrão, por servir ao estudo.
_Avoid_: Modo estudo

**Exam mode**:
Modo de Attempt em que o gabarito só aparece ao finalizar, como na prova real.
_Avoid_: Modo prova

**Review attempt**:
Attempt criado a partir de um filtro sobre Answers anteriores (erradas no último Attempt, erradas em qualquer Attempt, acertadas com *chute*, ou sem Confidence), em vez de um Exam completo. Fica fora da nota do Exam.
_Avoid_: Retry, refazer

**Drill**:
Attempt que sorteia Questions de uma única Section, tirando de todos os Exams de uma Certification. Prioriza inéditas e depois as erradas mais recentemente, salvo se o sorteio puramente aleatório estiver ligado. Fica fora da nota do Exam.
_Avoid_: Treino por section, quiz de section

**Question revision**:
Versão imutável do conteúdo de uma Question (texto, opções, gabarito, explicação), identificada por um hash do conteúdo. Cada Answer aponta para a revisão que o usuário viu.
_Avoid_: Versão, atualização

**Consistency**:
O quão estável é o acerto de uma mesma Question ao longo dos Attempts: *estável*, *aprendida*, *instável*, *errando* (últimos acertos todos errados) ou *poucos dados*.
_Avoid_: Retenção, fixação

**Topic**:
Assunto de uma Question, derivado da documentação AWS citada na explicação da Udemy. Cada Question tem um Topic principal (o mais citado) e zero ou mais secundários; dois Topics citados na mesma Question formam uma aresta.
_Avoid_: Tag, categoria, serviço

## Reflexão do usuário

**Confidence**:
O quão seguro o usuário estava ao dar uma Answer: *confiante*, *educated-guess* ou *chute*. Opcional.
_Avoid_: Certeza, nível de confiança

**Reasoning**:
Texto livre em que o usuário explica por que escolheu a Answer. Opcional.
_Avoid_: Justificativa, motivação

**AI Reasoning**:
Texto livre colado pelo usuário com a resolução da Question gerada por uma IA externa (Gemini no browser). Opcional.
_Avoid_: Explicação da IA, resolução
