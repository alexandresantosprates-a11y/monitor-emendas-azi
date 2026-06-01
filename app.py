"""
Web app do Monitor de Emendas — Paulo Azi
Flask + senha de acesso + geração automática do relatório
"""

import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from threading import Thread

from flask import (Flask, request, session, redirect, url_for,
                   render_template_string, jsonify, send_file)
from dotenv import load_dotenv

load_dotenv()

import database as db
import fetcher
import processor
import emailer

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "emendas-azi-2024-segredo")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENHA_ACESSO = os.getenv("SENHA_ACESSO", "pauloazi2024")
_atualizando = False


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Templates inline
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Emendas — Paulo Azi</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(135deg,#003DA5,#1a56db);min-height:100vh;
     display:flex;align-items:center;justify-content:center;font-family:'Segoe UI',Arial,sans-serif}
.card{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:400px;
      box-shadow:0 20px 60px rgba(0,0,0,.25);text-align:center}
.logo{font-size:36px;margin-bottom:8px}
h1{font-size:20px;font-weight:800;color:#003DA5;margin-bottom:4px}
p{font-size:13px;color:#64748b;margin-bottom:28px}
input{width:100%;padding:13px 16px;border:2px solid #e2e8f0;border-radius:10px;
      font-size:15px;outline:none;transition:.2s}
input:focus{border-color:#003DA5}
button{width:100%;margin-top:14px;padding:13px;background:#003DA5;color:#fff;
       border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;transition:.2s}
button:hover{background:#1a56db}
.erro{background:#fef2f2;color:#991b1b;padding:10px;border-radius:8px;
      font-size:13px;margin-bottom:14px}
</style>
</head>
<body>
<div class="card">
  <div class="logo">📊</div>
  <h1>Monitor de Emendas</h1>
  <p>Dep. Paulo Azi · Bahia</p>
  {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
  <form method="POST">
    <input type="password" name="senha" placeholder="Senha de acesso" autofocus required>
    <button type="submit">Entrar</button>
  </form>
</div>
</body>
</html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Emendas — Paulo Azi</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif}
.topbar{background:#003DA5;color:#fff;padding:12px 24px;display:flex;align-items:center;
        justify-content:space-between;position:sticky;top:0;z-index:100;
        box-shadow:0 2px 8px rgba(0,0,0,.2)}
.topbar h1{font-size:16px;font-weight:800}
.topbar p{font-size:11px;opacity:.7;margin-top:2px}
.actions{display:flex;gap:10px;align-items:center}
.btn{padding:8px 16px;border-radius:8px;font-size:12px;font-weight:700;
     cursor:pointer;border:none;text-decoration:none;display:inline-flex;align-items:center;gap:5px}
.btn-atualizar{background:#fff;color:#003DA5}
.btn-atualizar:hover{background:#e0e7ff}
.btn-pdf{background:#10b981;color:#fff}
.btn-pdf:hover{background:#059669}
.btn-sair{background:rgba(255,255,255,.15);color:#fff}
.btn-sair:hover{background:rgba(255,255,255,.25)}
.status{font-size:11px;color:rgba(255,255,255,.7);text-align:right}
.spinner{display:none;position:fixed;top:0;left:0;width:100%;height:100%;
         background:rgba(0,30,80,.7);z-index:999;align-items:center;justify-content:center}
.spinner.ativo{display:flex}
.spin-box{background:#fff;border-radius:16px;padding:40px 48px;text-align:center}
.spin-box p{font-size:15px;font-weight:700;color:#003DA5;margin-top:14px}
.spin-box small{font-size:12px;color:#64748b}
.spin{width:48px;height:48px;border:5px solid #e2e8f0;border-top-color:#003DA5;
      border-radius:50%;animation:spin 1s linear infinite;margin:0 auto}
@keyframes spin{to{transform:rotate(360deg)}}
iframe{width:100%;height:calc(100vh - 60px);border:none;display:block}
</style>
</head>
<body>

<div class="topbar">
  <div>
    <h1>📊 Monitor de Emendas — Dep. Paulo Azi</h1>
    <p>Bahia · Portal da Transparência · Atualizado: {{ ultima_atualizacao }}</p>
  </div>
  <div class="actions">
    <button class="btn btn-atualizar" onclick="atualizar()">🔄 Atualizar Dados</button>
    <a class="btn btn-pdf" href="/download" download>⬇ Baixar HTML</a>
    <a class="btn btn-sair" href="/sair">Sair</a>
  </div>
</div>

<div class="spinner" id="spinner">
  <div class="spin-box">
    <div class="spin"></div>
    <p>Atualizando dados...</p>
    <small>Buscando no Portal da Transparência. Aguarde.</small>
  </div>
</div>

<iframe src="/relatorio" id="frame"></iframe>

<script>
function atualizar() {
  document.getElementById('spinner').classList.add('ativo');
  fetch('/atualizar', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      document.getElementById('spinner').classList.remove('ativo');
      if (d.ok) document.getElementById('frame').src = '/relatorio?t=' + Date.now();
      else alert('Erro ao atualizar: ' + d.erro);
    })
    .catch(() => {
      document.getElementById('spinner').classList.remove('ativo');
      alert('Erro de conexão.');
    });
}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("senha") == SENHA_ACESSO:
            session["autenticado"] = True
            return redirect(url_for("dashboard"))
        return render_template_string(LOGIN_HTML, erro="Senha incorreta.")
    if session.get("autenticado"):
        return redirect(url_for("dashboard"))
    return render_template_string(LOGIN_HTML, erro=None)


@app.route("/dashboard")
@login_required
def dashboard():
    ultima = _ultima_atualizacao()
    return render_template_string(DASHBOARD_HTML, ultima_atualizacao=ultima)


@app.route("/relatorio")
@login_required
def relatorio():
    _garantir_dados()
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    html = emailer.gerar_html(resumo, alertas)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/download")
@login_required
def download():
    _garantir_dados()
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    caminho = emailer.salvar_html_local(resumo, alertas)
    return send_file(caminho, as_attachment=True,
                     download_name=f"emendas_paulo_azi_{datetime.now().strftime('%Y%m')}.html")


@app.route("/atualizar", methods=["POST"])
@login_required
def atualizar():
    global _atualizando
    if _atualizando:
        return jsonify({"ok": False, "erro": "Atualização já em andamento."})
    try:
        _atualizando = True
        _coletar_dados()
        _atualizando = False
        return jsonify({"ok": True})
    except Exception as e:
        _atualizando = False
        logger.error("Erro ao atualizar: %s", e)
        return jsonify({"ok": False, "erro": str(e)})


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coletar_dados():
    logger.info("Iniciando coleta de dados...")
    emendas_csv, convenios_csv = fetcher.carregar_csv_detalhado()
    processor.processar_emendas_csv(emendas_csv)
    processor.processar_convenios_csv(convenios_csv)
    db.registrar_coleta("web_app", len(emendas_csv), "OK")
    logger.info("Coleta concluída: %d emendas, %d convênios", len(emendas_csv), len(convenios_csv))


def _garantir_dados():
    """Se o banco estiver vazio (ex: reinício do servidor), coleta os dados."""
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM emendas")
    total = c.fetchone()[0]
    conn.close()
    if total == 0:
        logger.info("Banco vazio — coletando dados na inicialização...")
        _coletar_dados()


def _ultima_atualizacao() -> str:
    try:
        conn = db.get_connection()
        c = conn.cursor()
        c.execute("SELECT executado_em FROM coletas ORDER BY id DESC LIMIT 1")
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            dt = datetime.fromisoformat(row[0])
            return dt.strftime("%d/%m/%Y às %H:%M")
    except:
        pass
    return "nunca"


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

db.inicializar()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
