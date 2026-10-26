# App no Streamlit Community Cloud, com o banco no Turso

Para acessar o app do celular com custo R$ 0 e com o PC desligado, o app Streamlit roda no Streamlit Community Cloud (repositório privado no GitHub) e o banco passa a ser um libSQL hospedado no Turso, no lugar do `data/studies.db` local. O Community Cloud tem disco efêmero, então o SQLite em arquivo perderia o histórico de Attempts, que não dá para regerar; por isso o banco precisa morar fora do app.

Alternativas descartadas: VM Oracle Always Free com SQLite no disco (a mudança de código seria mínima, mas o cadastro da conta foi recusado), Google Drive como banco ao vivo (sem locking confiável), hospedar no próprio PC com túnel (depende do PC ligado) e Hugging Face Spaces (disco efêmero também).

O Drive entra só como destino de backup. O scraper e o `load` seguem no PC, porque dependem do browser e da sessão da Udemy; o `load` passa a gravar direto no Turso. O app local deixa de ser usado para estudar, para não haver dois históricos. O custo é a troca da conexão `sqlite3` pelo cliente libSQL (com latência de rede por consulta) e a dependência de dois free tiers de terceiros.
