SOBRAUTIL - Flask + MySQL

1. Instale Python e MySQL.
2. Abra a pasta do projeto no VS Code.
3. Crie e ative o ambiente virtual:

Linux:
  python3 -m venv venv
  source venv/bin/activate

Windows:
  python -m venv venv
  venv\Scripts\activate

4. Instale as bibliotecas:
  pip install -r requirements.txt

5. Edite config.py e coloque a senha real de sobrautil_user3.
   O banco esperado é sobrautil, com as tabelas do SQL fornecido.

6. Execute:
Linux:   python3 app.py
Windows: python app.py

7. Abra no navegador:
  http://127.0.0.1:5000

Páginas:
  /                 Página inicial
  /login            Entrar
  /painel            Painel (precisa entrar)
  /lotes             Listagem de lotes
  /lotes/novo        Cadastro de lote (precisa entrar)
  /doacoes           Lista de doações
  /doadores          Lista de doadores
  /ongs              Lista de ONGs
  /relatorios        Relatórios fiscais
  /sobre             Sobre o projeto

Observações:
- A página de login usa os usuários já cadastrados em Usuario.
- No SQL de exemplo, as senhas estão em texto simples. Isso é apenas para o protótipo.
  Em produção, use hash de senha (por exemplo werkzeug.security).
- O botão CADASTRAR/DOAR leva ao login nesta primeira versão; não existe formulário
  de cadastro de usuário novo implementado.
- A imagem do banner é carregada de uma URL externa do Unsplash; precisa de internet.
- app.secret_key deve ser substituída por uma chave privada antes de publicar.
