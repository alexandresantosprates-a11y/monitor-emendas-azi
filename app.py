"""
Web app do Monitor de Emendas — Paulo Azi
Flask + senha de acesso + carregamento em background
"""

import os
import logging
from datetime import datetime
from functools import wraps
from threading import Thread, Event

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

# Estado global da coleta
_status = {"pronto": False, "carregando": False, "erro": None, "ultima": None}


# ---------------------------------------------------------------------------
# Coleta em background
# ---------------------------------------------------------------------------

def _coletar_em_background():
    global _status
    if _status["carregando"]:
        return
    _status["carregando"] = True
    _status["erro"] = None
    try:
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
.overlay{display:none;position:fixed;inset:0;background:rgba(0,30,80,.75);
          z-index:999;align-items:center;justify-content:center}
.overlay.on{display:flex}
.box{background:#fff;border-radius:14px;padding:40px 48px;text-align:center}
.spin{width:44px;height:44px;border:5px solid #e2e8f0;border-top-color:#003DA5;
      border-radius:50%;animation:spin 1s linear infinite;margin:0 auto}
@keyframes spin{to{transform:rotate(360deg)}}
.box p{font-size:14px;font-weight:700;color:#003DA5;margin-top:14px}
.box small{font-size:11px;color:#64748b}
iframe{width:100%;height:calc(100vh - 52px);border:none;display:block}
</style>
</head>
<body>
<div class="bar">
  <div>
    <h1>📊 Monitor de Emendas — Dep. Paulo Azi</h1>
    <p>Bahia · Portal da Transparência · Última atualização: {{ ultima }}</p>
  </div>
  <div class="btns">
    <button class="btn b1" onclick="atualizar()">🔄 Atualizar Dados</button>
    <a class="btn b2" href="/download">⬇ Baixar HTML</a>
    <a class="btn b3" href="/sair">Sair</a>
  </div>
</div>
<div class="overlay" id="ov">
  <div class="box">
    <div class="spin"></div>
    <p>Atualizando dados...</p>
    <small>Buscando no Portal da Transparência. Aguarde ~1 minuto.</small>
  </div>
</div>
<iframe src="/relatorio" id="fr"></iframe>
<script>
function atualizar(){
  document.getElementById('ov').classList.add('on');
  fetch('/atualizar',{method:'POST'})
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('ov').classList.remove('on');
      if(d.ok) document.getElementById('fr').src='/relatorio?t='+Date.now();
      else alert('Erro: '+d.erro);
    })
    .catch(()=>{document.getElementById('ov').classList.remove('on');alert('Erro de conexão.');});
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
    if not _status["pronto"] and not _status["carregando"]:
        _iniciar_coleta()
    if not _status["pronto"]:
        return render_template_string(CARREGANDO_HTML, erro=_status.get("erro"))
    return render_template_string(DASHBOARD_HTML, ultima=_status["ultima"] or "—")


@app.route("/relatorio")
@login_required
def relatorio():
    if not _status["pronto"]:
        return render_template_string(CARREGANDO_HTML, erro=_status.get("erro"))
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    html = emailer.gerar_html(resumo, alertas)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/status")
@login_required
def status():
    return jsonify(_status)


@app.route("/atualizar", methods=["POST"])
@login_required
def atualizar():
    if _status["carregando"]:
        return jsonify({"ok": False, "erro": "Atualização já em andamento."})
    _iniciar_coleta()
    # Aguarda até 90s pela conclusão
    for _ in range(90):
        import time; time.sleep(1)
        if _status["pronto"] and not _status["carregando"]:
            return jsonify({"ok": True})
        if _status["erro"]:
            return jsonify({"ok": False, "erro": _status["erro"]})
    return jsonify({"ok": True})  # retorna mesmo se demorar — iframe vai atualizar


@app.route("/download")
@login_required
def download():
    if not _status["pronto"]:
        return "Dados ainda não carregados.", 503
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
# Startup — inicia coleta em background imediatamente
# ---------------------------------------------------------------------------

db.inicializar()
_iniciar_coleta()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
