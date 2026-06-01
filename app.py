"""
Web app do Monitor de Emendas — Paulo Azi
Flask + senha de acesso + carregamento em background
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from functools import wraps
from threading import Thread

from flask import (Flask, request, session, redirect, url_for,
                   render_template_string, jsonify, send_file)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "emendas-azi-2024-segredo")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENHA_ACESSO = os.getenv("SENHA_ACESSO", "AziEmendas2024")

# Detecta se está rodando no Render (modo estático)
MODO_ESTATICO = os.getenv("RENDER", "") != ""

# Caminho do relatório pré-gerado
STATIC_RELATORIO = os.path.join(os.path.dirname(__file__), "static", "relatorio.html")

# Estado global da coleta (usado apenas em modo local)
_status = {"pronto": False, "carregando": False, "erro": None, "ultima": None}


# ---------------------------------------------------------------------------
# Coleta em background (apenas modo local)
# ---------------------------------------------------------------------------

def _coletar_em_background():
    global _status
    if _status["carregando"]:
        return
    _status["carregando"] = True
    _status["erro"] = None
    try:
        import database as db
        import fetcher
        import processor
        import emailer
        logger.info("Iniciando coleta em background...")
        emendas_csv, convenios_csv = fetcher.carregar_csv_detalhado()
        processor.processar_emendas_csv(emendas_csv)
        processor.processar_convenios_csv(convenios_csv)
        db.registrar_coleta("web_app", len(emendas_csv), "OK")
        _status["pronto"] = True
        _status["ultima"] = datetime.now().strftime("%d/%m/%Y às %H:%M")
        logger.info("Coleta concluída: %d emendas", len(emendas_csv))
    except Exception as e:
        _status["erro"] = str(e)
        logger.error("Erro na coleta: %s", e)
    finally:
        _status["carregando"] = False


def _iniciar_coleta():
    t = Thread(target=_coletar_em_background, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("autenticado"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

LOGIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Emendas — Paulo Azi</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(135deg,#003DA5,#1a56db);min-height:100vh;
     display:flex;align-items:center;justify-content:center;font-family:'Segoe UI',Arial,sans-serif}
.card{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:380px;
      box-shadow:0 20px 60px rgba(0,0,0,.3);text-align:center}
.logo{font-size:40px;margin-bottom:10px}
h1{font-size:20px;font-weight:800;color:#003DA5;margin-bottom:4px}
p{font-size:13px;color:#64748b;margin-bottom:28px}
input{width:100%;padding:13px 16px;border:2px solid #e2e8f0;border-radius:10px;font-size:15px;outline:none}
input:focus{border-color:#003DA5}
button{width:100%;margin-top:12px;padding:13px;background:#003DA5;color:#fff;
       border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer}
button:hover{background:#1a56db}
.erro{background:#fef2f2;color:#991b1b;padding:10px;border-radius:8px;font-size:13px;margin-bottom:14px}
</style>
</head>
<body>
<div class="card">
  <div class="logo">📊</div>
  <h1>Monitor de Emendas</h1>
  <p>Dep. Paulo Azi · Bahia</p>
  {% if erro %}<div class="erro">{{ erro }}</div>{% endif %}
  <form method="POST" action="/">
    <input type="password" name="senha" placeholder="Senha de acesso" autofocus required>
    <button type="submit">Entrar</button>
  </form>
</div>
</body>
</html>"""

CARREGANDO_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Carregando — Monitor de Emendas</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(135deg,#003DA5,#1a56db);min-height:100vh;
     display:flex;align-items:center;justify-content:center;font-family:'Segoe UI',Arial,sans-serif}
.card{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:440px;
      box-shadow:0 20px 60px rgba(0,0,0,.3);text-align:center}
.spin{width:56px;height:56px;border:5px solid #e2e8f0;border-top-color:#003DA5;
      border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 20px}
@keyframes spin{to{transform:rotate(360deg)}}
h2{font-size:18px;font-weight:800;color:#003DA5;margin-bottom:8px}
p{font-size:13px;color:#64748b;line-height:1.6}
.eta{margin-top:16px;background:#f0f4ff;border-radius:8px;padding:12px;
     font-size:12px;color:#1d4ed8;font-weight:600}
.erro{background:#fef2f2;color:#991b1b;padding:12px;border-radius:8px;font-size:13px;margin-top:16px}
</style>
</head>
<body>
<div class="card">
  {% if erro %}
    <div style="font-size:40px;margin-bottom:16px">⚠️</div>
    <h2>Erro ao carregar</h2>
    <div class="erro">{{ erro }}</div>
    <p style="margin-top:16px"><a href="/dashboard" style="color:#003DA5;font-weight:700">Tentar novamente</a></p>
  {% else %}
    <div class="spin"></div>
    <h2>Buscando dados...</h2>
    <p>Estamos baixando as emendas parlamentares<br>do Portal da Transparência do Governo Federal.</p>
    <div class="eta">⏱ Primeira abertura demora cerca de 1 minuto. Esta página atualiza automaticamente.</div>
  {% endif %}
</div>
</body>
</html>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monitor de Emendas — Paulo Azi</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif}
.bar{background:#003DA5;color:#fff;padding:10px 20px;display:flex;
     align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.bar h1{font-size:15px;font-weight:800}
.bar p{font-size:10px;opacity:.7;margin-top:2px}
.btns{display:flex;gap:8px}
.btn{padding:7px 14px;border-radius:7px;font-size:12px;font-weight:700;
     cursor:pointer;border:none;text-decoration:none;display:inline-flex;align-items:center;gap:4px}
.b1{background:#fff;color:#003DA5}.b1:hover{background:#e0e7ff}
.b2{background:#10b981;color:#fff}.b2:hover{background:#059669}
.b3{background:rgba(255,255,255,.15);color:#fff}.b3:hover{background:rgba(255,255,255,.25)}
iframe{width:100%;height:calc(100vh - 52px);border:none;display:block}
</style>
</head>
<body>
<div class="bar">
  <div>
    <h1>📊 Monitor de Emendas — Dep. Paulo Azi</h1>
    <p>Bahia · Portal da Transparência · Atualizado em: {{ ultima }}</p>
  </div>
  <div class="btns">
    <a class="btn b2" href="/download">⬇ Baixar HTML</a>
    <a class="btn b3" href="/sair">Sair</a>
  </div>
</div>
<iframe src="/relatorio" id="fr"></iframe>
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
    if MODO_ESTATICO:
        # No Render: verifica se o arquivo estático existe
        if not os.path.exists(STATIC_RELATORIO):
            return render_template_string(CARREGANDO_HTML, erro="Relatório ainda não foi gerado. Gere localmente e faça push para o GitHub.")
        stat = os.stat(STATIC_RELATORIO)
        ultima = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y às %H:%M")
        return render_template_string(DASHBOARD_HTML, ultima=ultima)
    # Modo local: carrega do banco de dados
    if not _status["pronto"] and not _status["carregando"]:
        _iniciar_coleta()
    if not _status["pronto"]:
        return render_template_string(CARREGANDO_HTML, erro=_status.get("erro"))
    return render_template_string(DASHBOARD_HTML, ultima=_status["ultima"] or "—")


@app.route("/relatorio")
@login_required
def relatorio():
    if MODO_ESTATICO:
        if not os.path.exists(STATIC_RELATORIO):
            return "<p>Relatório ainda não disponível.</p>", 503
        with open(STATIC_RELATORIO, "r", encoding="utf-8") as f:
            html = f.read()
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}
    # Modo local
    if not _status["pronto"]:
        return render_template_string(CARREGANDO_HTML, erro=_status.get("erro"))
    import database as db
    import emailer
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    html = emailer.gerar_html(resumo, alertas)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/status")
@login_required
def status():
    if MODO_ESTATICO:
        tem_arquivo = os.path.exists(STATIC_RELATORIO)
        return jsonify({"pronto": tem_arquivo, "carregando": False, "erro": None,
                        "modo": "estatico"})
    return jsonify(_status)


@app.route("/download")
@login_required
def download():
    if MODO_ESTATICO:
        if not os.path.exists(STATIC_RELATORIO):
            return "Relatório ainda não disponível.", 503
        return send_file(STATIC_RELATORIO, as_attachment=True,
                         download_name=f"emendas_paulo_azi_{datetime.now().strftime('%Y%m')}.html")
    if not _status["pronto"]:
        return "Dados ainda não carregados.", 503
    import database as db
    import emailer
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    caminho = emailer.salvar_html_local(resumo, alertas)
    return send_file(caminho, as_attachment=True,
                     download_name=f"emendas_paulo_azi_{datetime.now().strftime('%Y%m')}.html")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Startup (apenas modo local)
# ---------------------------------------------------------------------------

if not MODO_ESTATICO:
    try:
        import database as db
        db.inicializar()
    except Exception as e:
        logger.error("Erro ao inicializar banco: %s", e)

    @app.before_request
    def inicializar_dados():
        if not _status["pronto"] and not _status["carregando"] and not _status["erro"]:
            _iniciar_coleta()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
