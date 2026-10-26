# Dashboard: calibração, ritmo e Consistency

Status: resolved
Blocked by: 09

Calibração por Confidence com 'sem marcação' à parte, ritmo (Questions por dia, tempo médio), Consistency por Question e agregada por Section e Certification (limiar configurável, 'poucos dados' abaixo de 3 Answers), mais erradas e acertadas sem confiança.

## Answer

Abas Calibração (com "Sem marcação" à parte), Ritmo (Questions por dia, tempo mediano e médio), Consistência (estável, aprendida, instável, errando, poucos dados; limiar de 2 a 6 configurável; por Section e total, sobre todo o histórico) e Questions (mais erradas e acertadas com chute). Decisões minhas: (1) incluí o nível "errando" (k erros seguidos), que o desenho original não cobria; (2) "acertadas sem confiança" virou "acertadas com Confidence chute". Cores validadas com o script da skill dataviz nos temas claro e escuro; `.streamlit/config.toml` põe o azul da paleta como cor primária.
