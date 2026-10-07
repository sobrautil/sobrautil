from flask import Flask, render_template
import mysql.connector
from config import DB_CONFIG


app = Flask(__name__)




def conectar():
   return mysql.connector.connect(**DB_CONFIG)




@app.route("/")
def index():
   try:
       conexao = conectar()


       if conexao.is_connected():
           conexao.close()
           return render_template("index.html")


   except Exception as erro:
       return f"Erro ao conectar: {erro}"


from flask import Flask, render_template
import mysql.connector
from config import DB_CONFIG

app = Flask(__name__)


def conectar():
    return mysql.connector.connect(**DB_CONFIG)


@app.route("/")
def index():
    try:
        conexao = conectar()
        if conexao.is_connected():
            conexao.close()
            return render_template("index.html")
    except Exception as erro:
        return f"Erro ao conectar: {erro}"


# --- ADICIONE AS NOVAS ROTAS ABAIXO ---

@app.route("/produtos")
def produtos():
    return render_template("produtos.html")

@app.route("/buscar")
def buscar():
    return render_template("buscar.html")

@app.route("/sobre")
def sobre():
    return render_template("sobre.html")

@app.route("/contato")
def contato():
    return render_template("contato.html")


if __name__ == "__main__":
    app.run(debug=True)


if __name__ == "__main__":
   app.run(debug=True)
