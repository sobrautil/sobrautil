from flask import (
    Flask, render_template, request, session,
    flash, redirect, url_for
)
from functools import wraps
from decimal import Decimal, InvalidOperation
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Necessária para session e flash.
# Em produção, utilize uma chave secreta guardada fora do código.
app.config["SECRET_KEY"] = "sobrautil-chave-local-trocar"


# ---------------- CONEXÃO COM O BANCO ----------------

def conectar():
    return mysql.connector.connect(**DB_CONFIG)


def consulta(sql, valores=(), uma=False):
    conexao = conectar()
    cursor = None

    try:
        cursor = conexao.cursor(dictionary=True)
        cursor.execute(sql, valores)

        if uma:
            return cursor.fetchone()

        return cursor.fetchall()

    finally:
        if cursor is not None:
            cursor.close()
        conexao.close()


# ---------------- AUTENTICAÇÃO ----------------

def exige_login(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if "idUsuario" not in session:
            flash(
                "Entre na sua conta para acessar essa página.",
                "aviso"
            )
            return redirect(url_for("login"))

        return funcao(*args, **kwargs)

    return wrapper


# ---------------- PÁGINA INICIAL ----------------

@app.route("/")
def index():
    dados = None

    try:
        dados = consulta("""
            SELECT
                (SELECT COUNT(*) FROM LoteAlimento)
                    AS total_lotes,
                (SELECT COUNT(*) FROM LoteAlimento
                    WHERE status = 'Disponível')
                    AS lotes_disponiveis,
                (SELECT COUNT(*) FROM Doacao)
                    AS total_doacoes,
                (SELECT COUNT(*) FROM ONG)
                    AS total_ongs
        """, uma=True)

    except Error as erro:
        app.logger.error("Erro ao consultar a página inicial: %s", erro)
        flash(
            "Não foi possível carregar os números. "
            "Confira o banco de dados.",
            "erro"
        )

    return render_template("index.html", dados=dados)


# ---------------- LOGIN E SAÍDA ----------------


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")

    try:
        usuario = consulta(
            """
            SELECT idUsuario, email, senha, statusCadastro, perfil
            FROM Usuario
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
            uma=True
        )

        senha_valida = False

        if usuario and usuario["senha"]:
            senha_salva = usuario["senha"]

            try:
                senha_valida = check_password_hash(senha_salva, senha)
            except (ValueError, TypeError):
                senha_valida = False

            # Compatibilidade com contas antigas
            if not senha_valida and senha_salva == senha:
                senha_valida = True

                conexao = None
                cursor = None

                try:
                    conexao = conectar()
                    cursor = conexao.cursor()

                    cursor.execute(
                        """
                        UPDATE Usuario
                        SET senha = %s
                        WHERE idUsuario = %s
                        """,
                        (
                            generate_password_hash(senha),
                            usuario["idUsuario"]
                        )
                    )

                    conexao.commit()

                except Error:
                    if conexao is not None:
                        conexao.rollback()

                    app.logger.exception(
                        "Erro ao atualizar a senha."
                    )
                    senha_valida = False

                finally:
                    if cursor is not None:
                        cursor.close()

                    if conexao is not None:
                        conexao.close()

        # Verifica se o login é válido
        if (
            not usuario
            or not senha_valida
            or (usuario["statusCadastro"] or "").lower() != "ativo"
        ):
            flash("E-mail ou senha inválidos, ou conta inativa.", "erro")
            return redirect(url_for("login"))

        # Verifica o perfil cadastrado
        perfil = (usuario.get("perfil") or "").lower()

        if perfil not in ("doador", "entidade", "contador"):
            flash("Sua conta não possui um perfil válido.", "erro")
            return redirect(url_for("login"))

        # Salva os dados da sessão
        session.clear()
        session["idUsuario"] = usuario["idUsuario"]
        session["email"] = usuario["email"]
        session["perfil"] = perfil

        flash("Login realizado com sucesso!", "sucesso")

        # Redireciona para o painel correspondente
        if perfil == "doador":
            return redirect(url_for("painel_doador"))

        elif perfil == "entidade":
            return redirect(url_for("painel_ong"))

        elif perfil == "contador":
            return redirect(url_for("painel_contador"))

    except Error:
        app.logger.exception("Erro ao verificar o login.")
        flash("Não foi possível acessar o banco de dados.", "erro")
        return redirect(url_for("login"))




# @app.route("/login", methods=["GET", "POST"])
# def login():
#     if request.method == "POST":
#         email = request.form.get("email", "").strip()
#         senha = request.form.get("senha", "")

#         try:
#             usuario = consulta("""
#                 SELECT idUsuario, email, senha, statusCadastro
#                 FROM Usuario
#                 WHERE email = %s
#                 LIMIT 1
#             """, (email,), uma=True)

#             if (
#                 usuario
#                 and usuario["senha"] == senha
#                 and usuario["statusCadastro"] == "Ativo"
#             ):
#                 session["idUsuario"] = usuario["idUsuario"]
#                 session["email"] = usuario["email"]

#                 flash("Login realizado com sucesso!", "sucesso")
#                 return redirect(url_for("painel"))

#             flash(
#                 "E-mail ou senha inválidos, ou cadastro inativo.",
#                 "erro"
#             )

#         except Error as erro:
#             app.logger.error("Erro no login: %s", erro)
#             flash("Não foi possível acessar o banco de dados.", "erro")

#     return render_template("login.html")


@app.route("/sair")
def sair():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("index"))


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "GET":
        return render_template("cadastro.html")

    perfil = request.form.get("perfil", "").strip().lower()
    nome = request.form.get("nome", "").strip()
    cnpj = request.form.get("cnpj", "").strip()
    telefone = request.form.get("telefone", "").strip()
    email = request.form.get("email", "").strip().lower()
    senha = request.form.get("senha", "")
    confirmar_senha = request.form.get("confirmar_senha", "")

    if perfil not in ("doador", "entidade", "contador"):
        flash("Selecione um perfil válido.", "erro")
        return redirect(url_for("cadastro"))


    if not all([nome, cnpj, telefone, email, senha, confirmar_senha]):
        flash("Preencha todos os campos.", "erro")
        return redirect(url_for("cadastro"))

    if senha != confirmar_senha:
        flash("As senhas não são iguais.", "erro")
        return redirect(url_for("cadastro"))

    if len(senha) < 8:
        flash("A senha deve ter pelo menos 8 caracteres.", "erro")
        return redirect(url_for("cadastro"))

    conexao = None
    cursor = None

    try:
        conexao = conectar()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute(
            "SELECT idUsuario FROM Usuario WHERE email = %s LIMIT 1",
            (email,)
        )

        if cursor.fetchone():
            flash("Já existe uma conta cadastrada com esse e-mail.", "erro")
            return redirect(url_for("cadastro"))

        senha_hash = generate_password_hash(senha)

        cursor.execute(
    """
    INSERT INTO Usuario
        (email, senha, telefone, statusCadastro, perfil)
    VALUES (%s, %s, %s, %s, %s)
    """,
    (email, senha_hash, telefone, "Ativo", perfil)
)

        id_usuario = cursor.lastrowid

        if perfil == "doador":
            cursor.execute(
                """
                INSERT INTO Doador
                    (idUsuario, cnpj, razaoSocial, regimeTributario)
                VALUES (%s, %s, %s, %s)
                """,
                (id_usuario, cnpj, nome, None)
            )

        elif perfil == "entidade":
            cursor.execute(
                """
                INSERT INTO ONG (idUsuario, cnpj, nomeInstituicao)
                VALUES (%s, %s, %s)
                """,
                (id_usuario, cnpj, nome)
            )

        conexao.commit()

        flash("Cadastro realizado! Entre com seu e-mail e senha.", "sucesso")
        return redirect(url_for("login"))

    except Error:
        if conexao is not None:
            conexao.rollback()

        app.logger.exception("Erro ao realizar cadastro no Sobrautil.")
        flash(
            "Não foi possível concluir o cadastro. "
            "Confira os dados e a conexão com o banco.",
            "erro"
        )
        return redirect(url_for("cadastro"))

    finally:
        if cursor is not None:
            cursor.close()
        if conexao is not None:
            conexao.close()


# ---------------- PAINEL ----------------

def exige_perfil(perfil_necessario):
    def decorador(funcao):
        @wraps(funcao)
        def wrapper(*args, **kwargs):

            if "idUsuario" not in session:
                flash("Faça login para acessar essa página.", "erro")
                return redirect(url_for("login"))

            if session.get("perfil") != perfil_necessario:
                flash("Você não tem permissão para acessar essa página.", "erro")
                return redirect(url_for("painel"))

            return funcao(*args, **kwargs)

        return wrapper
    return decorador


@app.route("/painel")
@exige_login
def painel():
    perfil = session.get("perfil")

    if perfil == "doador":
        return redirect(url_for("painel_doador"))

    elif perfil == "entidade":
        return redirect(url_for("painel_ong"))

    elif perfil == "contador":
        return redirect(url_for("painel_contador"))

    session.clear()
    return redirect(url_for("login"))



@app.route("/painel/doador")
@exige_perfil("doador")
def painel_doador():
    return render_template("dashboard.html")



@app.route("/painel/ong")
@exige_perfil("entidade")
def painel_ong():
    dados = consulta("""
        SELECT
            (SELECT COUNT(*) FROM LoteAlimento)
                AS total_lotes,
            (SELECT COUNT(*) FROM LoteAlimento
                WHERE status = 'Disponível')
                AS lotes_disponiveis,
            (SELECT COUNT(*) FROM Doacao)
                AS total_doacoes,
            (SELECT COUNT(*) FROM ONG)
                AS total_ongs,
            (SELECT COALESCE(SUM(valorTotalCusto), 0)
                FROM RelatorioFiscal)
                AS custos_fiscais
    """, uma=True)

    return render_template("dashboard.html", dados=dados)



@app.route("/painel/contador")
@exige_perfil("contador")
def painel_contador():
    return render_template("dashboard_contador.html")


# ---------------- LOTES ----------------


# ---------------- LOTES ----------------

@app.route("/lotes")
def lotes():
    registros = consulta("""
        SELECT
            l.idLote,
            l.descricao,
            l.quantidadeKg,
            l.dataValidade,
            l.valorCustoTotal,
            l.status,
            d.razaoSocial
        FROM LoteAlimento l
        LEFT JOIN Doador d
            ON d.idDoador = l.idDoador
        ORDER BY l.idLote DESC
    """)

    return render_template("lotes.html", lotes=registros)


@app.route("/lotes/novo", methods=["GET", "POST"])
@exige_login
def novo_lote():
    doadores = consulta("""
        SELECT idDoador, razaoSocial
        FROM Doador
        ORDER BY razaoSocial
    """)

    if request.method == "POST":
        try:
            id_doador = int(request.form["idDoador"])
            descricao = request.form["descricao"].strip()

            quantidade = Decimal(
                request.form["quantidadeKg"].replace(",", ".")
            )

            validade = request.form["dataValidade"]

            custo = Decimal(
                request.form["valorCustoTotal"].replace(",", ".") or "0"
            )

            status = request.form["status"]

            if not descricao:
                raise ValueError("Informe a descrição do lote.")

            if quantidade <= 0 or custo < 0:
                raise ValueError(
                    "A quantidade deve ser maior que zero "
                    "e o custo não pode ser negativo."
                )

            conexao = conectar()
            cursor = conexao.cursor()

            try:
                cursor.execute("""
                    INSERT INTO LoteAlimento
                    (
                        idDoador,
                        descricao,
                        quantidadeKg,
                        dataValidade,
                        valorCustoTotal,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    id_doador,
                    descricao,
                    quantidade,
                    validade,
                    custo,
                    status
                ))

                conexao.commit()

            finally:
                cursor.close()
                conexao.close()

            flash("Lote cadastrado com sucesso!", "sucesso")
            return redirect(url_for("lotes"))

        except (ValueError, InvalidOperation, KeyError) as erro:
            flash(f"Confira os dados informados: {erro}", "erro")

        except Error as erro:
            app.logger.error("Erro ao cadastrar lote: %s", erro)
            flash("Erro ao cadastrar lote no banco de dados.", "erro")

    return render_template("lote_form.html", doadores=doadores)


# ---------------- DOAÇÕES ----------------

@app.route("/doacoes")
def doacoes():
    registros = consulta("""
        SELECT
            do.idDoacao,
            do.dataReserva,
            do.tokenQRCode,
            do.statusDoacao,
            l.descricao,
            l.quantidadeKg,
            ong.nomeInstituicao
        FROM Doacao do
        LEFT JOIN LoteAlimento l
            ON l.idLote = do.idLote
        LEFT JOIN ONG ong
            ON ong.idONG = do.idONG
        ORDER BY do.idDoacao DESC
    """)

    return render_template("doacoes.html", doacoes=registros)


# ---------------- RELATÓRIOS ----------------

@app.route("/relatorios")
def relatorios():
    registros = consulta("""
        SELECT
            r.idRelatorio,
            r.mesAnoRef,
            r.valorTotalCusto,
            r.valorIncentivoEst,
            d.razaoSocial
        FROM RelatorioFiscal r
        LEFT JOIN Doador d
            ON d.idDoador = r.idDoador
        ORDER BY r.idRelatorio DESC
    """)

    totais = consulta("""
        SELECT
            COALESCE(SUM(valorTotalCusto), 0) AS custos,
            COALESCE(SUM(valorIncentivoEst), 0) AS incentivos
        FROM RelatorioFiscal
    """, uma=True)

    return render_template(
        "relatorios.html",
        relatorios=registros,
        totais=totais
    )


# ---------------- PRODUTOS, BUSCA E SOBRE ----------------

@app.route("/produtos")
def produtos():
    return render_template("produtos.html")


@app.route("/buscar")
def buscar():
    return render_template("buscar.html")


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


# ---------------- DOADORES ----------------

@app.route("/doadores")
def doadores():
    registros = consulta("""
        SELECT
            d.idDoador,
            d.cnpj,
            d.razaoSocial,
            d.regimeTributario,
            u.email,
            u.telefone
        FROM Doador d
        LEFT JOIN Usuario u
            ON u.idUsuario = d.idUsuario
        ORDER BY d.razaoSocial
    """)

    return render_template("doadores.html", doadores=registros)


# ---------------- ONGS ----------------

@app.route("/ongs")
def ongs():
    registros = consulta("""
        SELECT
            o.idONG,
            o.cnpj,
            o.nomeInstituicao,
            u.email,
            u.telefone
        FROM ONG o
        LEFT JOIN Usuario u
            ON u.idUsuario = o.idUsuario
        ORDER BY o.nomeInstituicao
    """)

    return render_template("ongs.html", ongs=registros)


# ---------------- CONTATO ----------------

@app.route("/contato")
def contato():
    return render_template("contato.html")


# ---------------- ERROS ----------------

@app.errorhandler(404)
def pagina_nao_encontrada(erro):
    return render_template("404.html"), 404


@app.errorhandler(Error)
def erro_banco(erro):
    app.logger.error("Erro de banco de dados: %s", erro)
    flash(
        "Ocorreu um problema ao consultar o banco de dados. "
        "Confira a configuração do MySQL.",
        "erro"
    )
    return redirect(url_for("index"))






if __name__ == "__main__":
    app.run(debug=True)