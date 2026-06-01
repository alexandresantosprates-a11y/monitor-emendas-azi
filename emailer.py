import os, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)


def _R(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"


def _pct(a, b) -> str:
    try:
        return f"{float(a)/float(b)*100:.0f}%" if float(b) else "0%"
    except:
        return "0%"


def _badge(s: str) -> str:
    s = (s or "").upper()
    if "PAGO" in s:
        return f'<span style="background:#d1fae5;color:#065f46;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700">PAGO</span>'
    if "LIQUID" in s:
        return f'<span style="background:#dbeafe;color:#1e40af;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700">LIQUIDADO</span>'
    if "EMPENH" in s:
        return f'<span style="background:#fef3c7;color:#92400e;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700">EMPENHADO</span>'
    return f'<span style="background:#f3f4f6;color:#374151;padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700">{s or "—"}</span>'


def _barra(pago, emp) -> str:
    try:
        pct = min(float(pago) / float(emp) * 100, 100) if float(emp) else 0
    except:
        pct = 0
    cor = "#10b981" if pct == 100 else ("#f59e0b" if pct > 0 else "#e5e7eb")
    return (f'<div style="background:#e5e7eb;border-radius:4px;height:7px;width:80px;display:inline-block;vertical-align:middle">'
            f'<div style="background:{cor};height:7px;border-radius:4px;width:{pct:.0f}%"></div></div>'
            f'<span style="font-size:10px;color:#6b7280;margin-left:4px">{pct:.0f}%</span>')


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;padding:16px}
.wrap{max-width:980px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.12)}
.hdr{background:linear-gradient(135deg,#003DA5,#1a56db);color:#fff;padding:28px 36px}
.hdr h1{font-size:22px;font-weight:800;letter-spacing:-.3px}
.hdr p{font-size:12px;opacity:.75;margin-top:5px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr)}
.kpi{padding:18px 20px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;text-align:center}
.kpi:last-child{border-right:none}
.kv{font-size:19px;font-weight:800;color:#003DA5}
.kl{font-size:10px;color:#64748b;margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
.sec{padding:24px 36px;border-bottom:1px solid #e2e8f0}
.sec:last-child{border-bottom:none}
h2{font-size:12px;color:#003DA5;margin:0 0 14px;text-transform:uppercase;letter-spacing:.7px;font-weight:800}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#f8fafc;color:#475569;padding:9px 10px;text-align:left;font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #e2e8f0;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:hover td{background:#f8fafc}
.municipio{font-weight:600;color:#0f172a}
.objeto{color:#374151;font-style:italic;font-size:11px;max-width:280px}
.footer{background:#f8fafc;padding:14px 36px;font-size:10px;color:#94a3b8;text-align:center}
.alerta{border-left:4px solid #f59e0b;background:#fffbeb;padding:10px 14px;margin-bottom:7px;border-radius:0 5px 5px 0;font-size:12px}
.alerta.pago{border-left-color:#10b981;background:#ecfdf5}
.tag{background:#eff6ff;color:#1d4ed8;padding:1px 7px;border-radius:8px;font-size:10px;font-weight:600;margin-right:3px}
"""


def _secao_alertas(alertas: list) -> str:
    if not alertas:
        return ""
    itens = ""
    for a in alertas[:20]:
        cls = "pago" if a["tipo"] == "NOVO_PAGAMENTO" else ""
        icone = "💰" if cls else "🔔"
        itens += f'<div class="alerta {cls}">{icone} {a["descricao"]} — <strong>{_R(a.get("valor",0))}</strong></div>'
    return f'<div class="sec"><h2>🔔 Novidades detectadas ({len(alertas)})</h2>{itens}</div>'


def _tabela_convenios(convenios: list) -> str:
    if not convenios:
        return "<tr><td colspan='7' style='text-align:center;color:#9ca3af;padding:20px'>Nenhum convênio encontrado</td></tr>"
    # Agrupar por categoria para facilitar leitura
    por_cat: dict = {}
    for c in convenios:
        cat = c.get("categoria") or "Outros"
        por_cat.setdefault(cat, []).append(c)

    linhas = ""
    for cat, itens in sorted(por_cat.items()):
        linhas += (f'<tr><td colspan="7" style="background:#f0f4ff;font-weight:800;'
                   f'color:#003DA5;padding:8px 10px;font-size:11px">'
                   f'▸ {cat.upper()} — {len(itens)} convênios</td></tr>')
        for c in sorted(itens, key=lambda x: x.get("municipio") or ""):
            municipio = c.get("municipio") or c.get("localidade") or "—"
            uf = c.get("uf") or "BA"
            objeto = (c.get("objeto") or "—")
            objeto_curto = objeto[:100] + "..." if len(objeto) > 100 else objeto
            numero = c.get("numero") or "—"
            data = c.get("data_publicacao") or "—"
            convenente = c.get("convenente") or "—"
            valor = _R(c.get("valor") or 0)
            ano = c.get("ano") or "—"
            status = c.get("status") or ""
            linhas += (
                f"<tr>"
                f"<td><span class='municipio'>{municipio}/{uf}</span><br>"
                f"<span style='font-size:10px;color:#6b7280'>{convenente}</span></td>"
                f"<td class='objeto' title='{objeto}'>{objeto_curto}</td>"
                f"<td style='text-align:center'>{ano}</td>"
                f"<td style='font-size:11px;color:#6b7280'>{data}</td>"
                f"<td style='font-size:11px;color:#6b7280'>{numero}</td>"
                f"<td style='text-align:right;font-weight:700'>{valor}</td>"
                f"<td>{_badge(status)}</td>"
                f"</tr>"
            )
    return linhas


def _tabela_municipios(top: list) -> str:
    linhas = ""
    for i, r in enumerate(top, 1):
        linhas += (
            f"<tr>"
            f"<td style='font-weight:700;color:#003DA5'>{i}</td>"
            f"<td class='municipio'>{r['municipio']}/{r['uf']}</td>"
            f"<td style='text-align:center'>{r['emendas']}</td>"
            f"<td style='text-align:right;font-weight:700'>{_R(r['empenhado'])}</td>"
            f"<td style='text-align:right;color:#10b981'>{_R(r['pago'])}</td>"
            f"<td>{_barra(r['pago'], r['empenhado'])}</td>"
            f"</tr>"
        )
    return linhas


def _tabela_categorias(cats: list) -> str:
    linhas = ""
    for r in cats:
        linhas += (
            f"<tr>"
            f"<td style='font-weight:700'>{r['categoria']}</td>"
            f"<td style='text-align:center'>{r['emendas']}</td>"
            f"<td style='text-align:right'>{_R(r['empenhado'])}</td>"
            f"<td style='text-align:right;color:#10b981'>{_R(r['pago'])}</td>"
            f"<td>{_barra(r['pago'], r['empenhado'])}</td>"
            f"</tr>"
        )
    return linhas


def _tabela_ano(anos: list) -> str:
    linhas = ""
    for r in anos:
        linhas += (
            f"<tr>"
            f"<td style='font-weight:800'>{r['ano']}</td>"
            f"<td style='text-align:center'>{r['emendas']}</td>"
            f"<td style='text-align:right'>{_R(r['empenhado'])}</td>"
            f"<td style='text-align:right'>{_R(r['liquidado'])}</td>"
            f"<td style='text-align:right;color:#10b981;font-weight:700'>{_R(r['pago'])}</td>"
            f"<td>{_barra(r['pago'], r['empenhado'])}</td>"
            f"</tr>"
        )
    return linhas


def gerar_html(resumo: dict, alertas: list) -> str:
    t = resumo.get("totais") or {}
    total_e = t.get("total_empenhado") or 0
    total_p = t.get("total_pago") or 0
    total_a = t.get("total_a_pagar") or 0
    total_qt = t.get("total_emendas") or 0
    conv_qt = len(resumo.get("convenios") or [])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Emendas Paulo Azi — {datetime.now().strftime('%m/%Y')}</title>
<style>{CSS}</style>
</head>
<body><div class="wrap">

<div class="hdr">
  <h1>Monitor de Emendas Parlamentares — Dep. Paulo Azi</h1>
  <p>Bahia · Dados do Portal da Transparência (CGU) · Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="kv">{total_qt}</div><div class="kl">Emendas únicas</div></div>
  <div class="kpi"><div class="kv">{_R(total_e)}</div><div class="kl">Total empenhado</div></div>
  <div class="kpi"><div class="kv">{_R(total_p)}</div><div class="kl">Total pago</div></div>
  <div class="kpi"><div class="kv">{_R(total_a)}</div><div class="kl">A receber</div></div>
</div>

{_secao_alertas(alertas)}

<div class="sec">
  <h2>Convênios por Município e Objeto — Detalhamento Completo ({conv_qt} convênios)</h2>
  <p style="font-size:11px;color:#6b7280;margin-bottom:12px">Objeto exato de cada convênio por município beneficiado, agrupado por área de atuação</p>
  <div style="overflow-x:auto">
  <table>
    <tr>
      <th>Município / Convenente</th>
      <th>Objeto do Convênio</th>
      <th style="text-align:center">Ano</th>
      <th>Data</th>
      <th>Nº Convênio</th>
      <th style="text-align:right">Valor</th>
      <th>Status</th>
    </tr>
    {_tabela_convenios(resumo.get("convenios") or [])}
  </table>
  </div>
</div>

<div class="sec">
  <h2>Top Municípios Beneficiados</h2>
  <div style="overflow-x:auto">
  <table>
    <tr><th>#</th><th>Município</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th>
        <th style="text-align:right">Pago</th><th>Execução</th></tr>
    {_tabela_municipios(resumo.get("top_municipios") or [])}
  </table>
  </div>
</div>

<div class="sec">
  <h2>Por Área de Atuação</h2>
  <table>
    <tr><th>Área</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th>
        <th style="text-align:right">Pago</th><th>Execução</th></tr>
    {_tabela_categorias(resumo.get("por_categoria") or [])}
  </table>
</div>

<div class="sec">
  <h2>Histórico Anual</h2>
  <table>
    <tr><th>Ano</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th>
        <th style="text-align:right">Liquidado</th>
        <th style="text-align:right">Pago</th><th>Execução</th></tr>
    {_tabela_ano(resumo.get("por_ano") or [])}
  </table>
</div>

<div class="sec">
  <h2>Por Status de Execução</h2>
  <table>
    <tr><th>Status</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th>
        <th style="text-align:right">Pago</th></tr>
    {"".join(
        f"<tr><td>{_badge(r['status'])}</td><td style='text-align:center'>{r['emendas']}</td>"
        f"<td style='text-align:right'>{_R(r['empenhado'])}</td><td style='text-align:right'>{_R(r['pago'])}</td></tr>"
        for r in (resumo.get("por_status") or [])
    )}
  </table>
</div>

<div class="footer">
  Monitor de Emendas Parlamentares · Dep. Paulo Azi (BA) · Código do autor: 3738<br>
  Fonte: Portal da Transparência do Governo Federal — portaldatransparencia.gov.br<br>
  {datetime.now().strftime('%d/%m/%Y %H:%M')}
</div>
</div></body></html>"""


def salvar_html_local(resumo: dict, alertas: list) -> str:
    html = gerar_html(resumo, alertas)
    pasta = os.path.join(os.path.dirname(__file__), "relatorios")
    os.makedirs(pasta, exist_ok=True)
    nome = f"relatorio_{datetime.now().strftime('%Y%m')}.html"
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Relatório salvo: %s", caminho)
    return caminho


def enviar_relatorio(resumo: dict, alertas: list) -> bool:
    remetente = os.getenv("EMAIL_REMETENTE", "")
    senha = os.getenv("EMAIL_SENHA", "")
    smtp_host = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    destinatarios_raw = os.getenv("EMAIL_DESTINATARIOS", "")

    if not remetente or not senha or not destinatarios_raw:
        logger.error("Configure EMAIL_REMETENTE, EMAIL_SENHA e EMAIL_DESTINATARIOS no .env")
        return False

    destinatarios = [d.strip() for d in destinatarios_raw.split(",") if d.strip()]
    html = gerar_html(resumo, alertas)
    mes = datetime.now().strftime("%B/%Y")
    assunto = f"Emendas Paulo Azi — Relatório {mes} ({len(resumo.get('convenios',[]))} convênios)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.ehlo(); s.starttls(); s.login(remetente, senha)
            s.sendmail(remetente, destinatarios, msg.as_string())
        logger.info("Relatório enviado para: %s", destinatarios)
        return True
    except Exception as e:
        logger.error("Falha ao enviar: %s", e)
        return False
