from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG

app = Flask(__name__)
app.secret_key = "troque-esta-chave-por-uma-chave-secreta"


def conectar():
    return mysql.connector.connect(**DB_CONFIG)


def consulta(sql, valores=(), uma=False):
    conexao = conectar()
    cursor = conexao.cursor(dictionary=True)
    try:
        cursor.execute(sql, valores)
        resultado = cursor.fetchone() if uma else cursor.fetchall()
        return resultado
    finally:
        cursor.close()
        conexao.close()


def exige_login(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if "idUsuario" not in session:
            flash("Entre na sua conta para acessar essa página.", "aviso")
            return redirect(url_for("login"))
        return funcao(*args, **kwargs)
    return wrapper


@app.route("/")
def index():
    try:
        dados = consulta("""
            SELECT
                (SELECT COUNT(*) FROM LoteAlimento) AS total_lotes,
                (SELECT COUNT(*) FROM LoteAlimento WHERE status = 'Disponível') AS lotes_disponiveis,
                (SELECT COUNT(*) FROM Doacao) AS total_doacoes,
                (SELECT COUNT(*) FROM ONG) AS total_ongs
        """, uma=True)
        return render_template("index.html", dados=dados)
    except Error as erro:
        return render_template("index.html", dados=None, erro_db=str(erro))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        try:
            usuario = consulta(
                """SELECT idUsuario, email, senha, statusCadastro
                   FROM Usuario WHERE email = %s LIMIT 1""",
                (email,), uma=True
            )
            # A tabela fornecida guarda senha em texto simples. Para um sistema real,
            # armazene hashes com werkzeug.security e migre as senhas existentes.
            if usuario and usuario["senha"] == senha and usuario["statusCadastro"] == "Ativo":
                session["idUsuario"] = usuario["idUsuario"]
                session["email"] = usuario["email"]
                flash("Login realizado com sucesso!", "sucesso")
                return redirect(url_for("painel"))
            flash("E-mail ou senha inválidos, ou cadastro inativo.", "erro")
        except Error as erro:
            flash(f"Não foi possível acessar o banco: {erro}", "erro")
    return render_template("login.html")


@app.route("/sair")
def sair():
    session.clear()
    flash("Você saiu da sua conta.", "sucesso")
    return redirect(url_for("index"))


@app.route("/painel")
@exige_login
def painel():
    dados = consulta("""
        SELECT
            (SELECT COUNT(*) FROM LoteAlimento) AS total_lotes,
            (SELECT COUNT(*) FROM LoteAlimento WHERE status = 'Disponível') AS lotes_disponiveis,
            (SELECT COUNT(*) FROM Doacao) AS total_doacoes,
            (SELECT COUNT(*) FROM ONG) AS total_ongs,
            (SELECT COALESCE(SUM(valorTotalCusto), 0) FROM RelatorioFiscal) AS custos_fiscais
    """, uma=True)
    return render_template("dashboard.html", dados=dados)


@app.route("/lotes")
def lotes():
    registros = consulta("""
        SELECT l.idLote, l.descricao, l.quantidadeKg, l.dataValidade,
               l.valorCustoTotal, l.status, d.razaoSocial
        FROM LoteAlimento l
        LEFT JOIN Doador d ON d.idDoador = l.idDoador
        ORDER BY l.idLote DESC
    """)
    return render_template("lotes.html", lotes=registros)


@app.route("/lotes/novo", methods=["GET", "POST"])
@exige_login
def novo_lote():
    doadores = consulta("SELECT idDoador, razaoSocial FROM Doador ORDER BY razaoSocial")
    if request.method == "POST":
        try:
            id_doador = int(request.form["idDoador"])
            descricao = request.form["descricao"].strip()
            quantidade = Decimal(request.form["quantidadeKg"].replace(",", "."))
            validade = request.form["dataValidade"]
            custo = Decimal(request.form["valorCustoTotal"].replace(",", ".") or "0")
            status = request.form["status"]
            if quantidade <= 0 or custo < 0:
                raise ValueError("A quantidade deve ser maior que zero e o custo não pode ser negativo.")
            conexao = conectar()
            cursor = conexao.cursor()
            cursor.execute("""
                INSERT INTO LoteAlimento
                (idDoador, descricao, quantidadeKg, dataValidade, valorCustoTotal, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (id_doador, descricao, quantidade, validade, custo, status))
            conexao.commit()
            cursor.close()
            conexao.close()
            flash("Lote cadastrado com sucesso!", "sucesso")
            return redirect(url_for("lotes"))
        except (ValueError, InvalidOperation, KeyError) as erro:
            flash(f"Confira os dados informados: {erro}", "erro")
        except Error as erro:
            flash(f"Erro ao cadastrar lote: {erro}", "erro")
    return render_template("lote_form.html", doadores=doadores)


@app.route("/doacoes")
def doacoes():
    registros = consulta("""
        SELECT do.idDoacao, do.dataReserva, do.tokenQRCode, do.statusDoacao,
               l.descricao, l.quantidadeKg, ong.nomeInstituicao
        FROM Doacao do
        LEFT JOIN LoteAlimento l ON l.idLote = do.idLote
        LEFT JOIN ONG ong ON ong.idONG = do.idONG
        ORDER BY do.idDoacao DESC
    """)
    return render_template("doacoes.html", doacoes=registros)


@app.route("/relatorios")
def relatorios():
    registros = consulta("""
        SELECT r.idRelatorio, r.mesAnoRef, r.valorTotalCusto,
               r.valorIncentivoEst, d.razaoSocial
        FROM RelatorioFiscal r
        LEFT JOIN Doador d ON d.idDoador = r.idDoador
        ORDER BY r.idRelatorio DESC
    """)
    totais = consulta("""
        SELECT COALESCE(SUM(valorTotalCusto), 0) AS custos,
               COALESCE(SUM(valorIncentivoEst), 0) AS incentivos
        FROM RelatorioFiscal
    """, uma=True)
    return render_template("relatorios.html", relatorios=registros, totais=totais)


@app.route("/sobre")
def sobre():
    return render_template("sobre.html")


@app.route("/doadores")
def doadores():
    registros = consulta("""
        SELECT d.idDoador, d.cnpj, d.razaoSocial, d.regimeTributario, u.email, u.telefone
        FROM Doador d
        LEFT JOIN Usuario u ON u.idUsuario = d.idUsuario
        ORDER BY d.razaoSocial
    """)
    return render_template("doadores.html", doadores=registros)


@app.route("/ongs")
def ongs():
    registros = consulta("""
        SELECT o.idONG, o.cnpj, o.nomeInstituicao, u.email, u.telefone
        FROM ONG o
        LEFT JOIN Usuario u ON u.idUsuario = o.idUsuario
        ORDER BY o.nomeInstituicao
    """)
    return render_template("ongs.html", ongs=registros)


@app.errorhandler(404)
def pagina_nao_encontrada(_erro):
    return render_template("404.html"), 404


@app.errorhandler(Error)
def erro_banco(_erro):
    flash("Ocorreu um problema ao consultar o banco de dados. Confira a configuração do MySQL.", "erro")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
