import os, smtplib, logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

PARLAMENTAR = os.getenv("PARLAMENTAR_NOME", "PAULO AZI")
CODIGO_AUTOR = os.getenv("PARLAMENTAR_CODIGO", "3738")


def _R(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "R$ 0,00"


def _Rm(v) -> str:
    try:
        f = float(v)
        if f >= 1_000_000:
            return f"R$ {f/1_000_000:.1f}M"
        if f >= 1_000:
            return f"R$ {f/1_000:.0f}K"
        return _R(v)
    except:
        return "R$ 0"


def _badge(s: str) -> str:
    s = (s or "").upper()
    if "PAGO" in s:
        return '<span style="background:#d1fae5;color:#065f46;padding:2px 9px;border-radius:10px;font-size:10px;font-weight:700">✓ PAGO</span>'
    if "LIQUID" in s:
        return '<span style="background:#dbeafe;color:#1e40af;padding:2px 9px;border-radius:10px;font-size:10px;font-weight:700">LIQUIDADO</span>'
    if "EMPENH" in s:
        return '<span style="background:#fef3c7;color:#92400e;padding:2px 9px;border-radius:10px;font-size:10px;font-weight:700">EMPENHADO</span>'
    return f'<span style="background:#f3f4f6;color:#374151;padding:2px 9px;border-radius:10px;font-size:10px;font-weight:700">{s or "—"}</span>'


def _badge_cat(cat: str) -> str:
    cores = {
        "Saúde": "#fce7f3;color:#9d174d",
        "Urbanismo": "#e0f2fe;color:#0369a1",
        "Educação": "#fef9c3;color:#713f12",
        "Assistência Social": "#f0fdf4;color:#166534",
        "Desporto e Lazer": "#ede9fe;color:#5b21b6",
        "Encargos Especiais": "#f1f5f9;color:#475569",
        "Cultura e Esporte": "#fff7ed;color:#9a3412",
        "Cultura": "#fff7ed;color:#9a3412",
        "Indústria": "#ecfdf5;color:#065f46",
        "Segurança Pública": "#fef2f2;color:#991b1b",
        "Direitos da Cidadania": "#f5f3ff;color:#4c1d95",
        "Infraestrutura": "#e0f2fe;color:#0369a1",
    }
    estilo = cores.get(cat, "#f3f4f6;color:#374151")
    return f'<span style="background:{estilo};padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700">{cat}</span>'


def _titulo_acao(acao: str) -> str:
    if not acao:
        return "Ação não especificada"
    return acao.strip().capitalize()


def _barra(rec, emp, largura=100) -> str:
    try:
        pct = min(float(rec) / float(emp) * 100, 100) if float(emp) else 0
    except:
        pct = 0
    cor = "#10b981" if pct >= 90 else ("#f59e0b" if pct >= 40 else "#3b82f6")
    return (
        f'<div style="background:#e5e7eb;border-radius:4px;height:6px;width:{largura}px;'
        f'display:inline-block;vertical-align:middle">'
        f'<div style="background:{cor};height:6px;border-radius:4px;width:{pct:.0f}%"></div>'
        f'</div> <span style="font-size:10px;color:#6b7280">{pct:.0f}%</span>'
    )


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#f0f4f8;font-family:'Segoe UI',Arial,sans-serif;color:#1e293b;padding:16px}
.wrap{max-width:1060px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.1)}
.hdr{background:linear-gradient(135deg,#003DA5,#1a56db);color:#fff;padding:28px 36px}
.hdr h1{font-size:21px;font-weight:800}
.hdr p{font-size:12px;opacity:.7;margin-top:5px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr)}
.kpi{padding:18px 20px;border-right:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;text-align:center}
.kpi:last-child{border-right:none}
.kv{font-size:20px;font-weight:800;color:#003DA5}
.kl{font-size:10px;color:#64748b;margin-top:3px;text-transform:uppercase;letter-spacing:.5px}
.sec{padding:24px 36px;border-bottom:1px solid #e2e8f0}
.sec:last-child{border-bottom:none}
h2{font-size:12px;color:#003DA5;margin:0 0 14px;text-transform:uppercase;letter-spacing:.7px;font-weight:800}
table{width:100%;border-collapse:collapse;font-size:12px}
th{background:#f8fafc;color:#475569;padding:9px 10px;text-align:left;font-weight:700;font-size:10px;
   text-transform:uppercase;letter-spacing:.4px;border-bottom:2px solid #e2e8f0;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #f1f5f9;vertical-align:top}
tr:hover td{background:#fafbfc}
.mun-card{border:1px solid #e2e8f0;border-radius:10px;margin-bottom:12px;overflow:hidden}
.mun-hdr{background:#f8fafc;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e2e8f0}
.mun-nome{font-size:14px;font-weight:800;color:#003DA5}
.mun-total{font-size:15px;font-weight:800;color:#10b981}
.mun-body{padding:0}
.repasse{padding:11px 16px;border-bottom:1px solid #f1f5f9;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start}
.repasse:last-child{border-bottom:none}
.repasse:hover{background:#f8fafc}
.rep-nome{font-size:11px;font-weight:700;color:#1e293b}
.rep-acao{font-size:12px;color:#1e293b;margin-top:3px;line-height:1.4;font-style:italic}
.rep-meta{font-size:10px;color:#94a3b8;margin-top:4px;display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.rep-val{font-size:14px;font-weight:800;color:#003DA5;white-space:nowrap;text-align:right}
.emenda-card{border:1px solid #e2e8f0;border-radius:8px;padding:14px 16px;margin-bottom:10px}
.emenda-card:hover{border-color:#c7d2fe;background:#fafbff}
.footer{background:#f8fafc;padding:14px 36px;font-size:10px;color:#94a3b8;text-align:center}
.nota{background:#eff6ff;border-left:4px solid #3b82f6;padding:10px 16px;font-size:11px;color:#1e3a5f;margin-bottom:14px;border-radius:0 6px 6px 0}
.alerta{border-left:4px solid #f59e0b;background:#fffbeb;padding:10px 14px;margin-bottom:7px;border-radius:0 5px 5px 0;font-size:12px}
.alerta.pago{border-left-color:#10b981;background:#ecfdf5}
.ano-bloco{background:#f0f4ff;border-radius:8px;padding:8px 14px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
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


def _secao_emendas(todas: list) -> str:
    por_ano: dict = {}
    for e in todas:
        if e.get("rn", 1) != 1:
            continue
        ano = e.get("ano") or "—"
        por_ano.setdefault(ano, []).append(e)

    html = ""
    for ano in sorted(por_ano.keys(), reverse=True):
        emendas = por_ano[ano]
        total_ano = sum(e.get("valor_empenhado") or 0 for e in emendas)
        html += (
            f'<div class="ano-bloco">'
            f'<span style="font-weight:800;color:#003DA5;font-size:14px">Ano {ano}</span>'
            f'<span style="font-weight:700;color:#003DA5">{_Rm(total_ano)} empenhados · '
            f'{len(emendas)} emenda{"s" if len(emendas)>1 else ""}</span>'
            f'</div>'
        )
        for e in emendas:
            acao = _titulo_acao(e.get("acao") or e.get("subfuncao") or "")
            municipio = e.get("municipio") or ""
            if not municipio or municipio in ("Sem Informação", "Múltiplo", "Sem_Informação"):
                municipio = "Bahia (distribuição estadual)"
            else:
                municipio = f"{municipio}/{e.get('uf','BA')}"
            cat = e.get("categoria") or "Outros"
            emp = e.get("valor_empenhado") or 0
            pago = e.get("valor_pago") or 0
            status = e.get("status") or ""
            subfuncao = e.get("subfuncao") or ""
            programa = e.get("programa") or ""
            tipo = e.get("tipo") or ""
            is_pix = "Especiais" in tipo

            html += f"""
<div class="emenda-card">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
    <div style="flex:1">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;flex-wrap:wrap">
        {_badge_cat(cat)}
        {'<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:700">PIX / Livre destinação</span>' if is_pix else ''}
        {_badge(status)}
      </div>
      <div style="font-size:13px;font-weight:700;color:#1e293b;margin-bottom:4px;line-height:1.4">{acao}</div>
      <div style="font-size:11px;color:#64748b;margin-bottom:3px">
        📍 <strong>{municipio}</strong>
        {f' &nbsp;·&nbsp; {subfuncao}' if subfuncao else ''}
      </div>
      {f'<div style="font-size:10px;color:#94a3b8;margin-top:2px">{programa[:100]}</div>' if programa and programa.lower()[:30] != acao.lower()[:30] else ''}
    </div>
    <div style="text-align:right;min-width:140px">
      <div style="font-size:17px;font-weight:800;color:#003DA5">{_R(emp)}</div>
      <div style="font-size:10px;color:#64748b;margin-top:1px">empenhado</div>
      {f'<div style="font-size:12px;color:#10b981;font-weight:700;margin-top:5px">{_R(pago)} pago</div>' if pago > 0 else ''}
      <div style="margin-top:6px">{_barra(pago, emp, 110)}</div>
    </div>
  </div>
</div>"""
    return html


def _secao_municipios(municipios_detalhados: list) -> str:
    if not municipios_detalhados:
        return "<p style='color:#9ca3af;text-align:center;padding:20px'>Sem dados de municípios disponíveis.</p>"

    html = ""
    for mun in municipios_detalhados:
        nome = mun["municipio"]
        total = mun["total"]
        repasses = mun["repasses"]
        n_emendas = len(set(r["codigo_emenda"] for r in repasses))

        html += f"""
<div class="mun-card">
  <div class="mun-hdr">
    <div>
      <div class="mun-nome">📍 {nome} — {mun.get('uf','BA')}</div>
      <div style="font-size:10px;color:#64748b;margin-top:2px">
        {n_emendas} emenda{"s" if n_emendas!=1 else ""} · {len(repasses)} repasse{"s" if len(repasses)!=1 else ""}
      </div>
    </div>
    <div class="mun-total">{_R(total)}</div>
  </div>
  <div class="mun-body">"""

        for rep in sorted(repasses, key=lambda x: -(x["recebido"] or 0)):
            favorecido = (rep["favorecido"] or "").title()
            acao = _titulo_acao(rep.get("acao") or rep.get("subfuncao") or "")
            subfuncao = rep.get("subfuncao") or ""
            cat = rep.get("categoria") or ""
            ano = rep.get("ano") or "—"
            status = rep.get("status") or ""
            recebido = rep.get("recebido") or 0
            tipo = rep.get("tipo") or ""
            is_pix = "Especiais" in tipo

            html += f"""
    <div class="repasse">
      <div>
        <div class="rep-nome">{favorecido}</div>
        <div class="rep-acao">{acao}</div>
        <div class="rep-meta">
          {_badge_cat(cat) if cat else ''}
          {'&nbsp;<span style="background:#fef3c7;color:#92400e;padding:1px 6px;border-radius:6px;font-size:9px;font-weight:700">PIX</span>' if is_pix else ''}
          {f'&nbsp;<span style="color:#94a3b8">{subfuncao}</span>' if subfuncao and subfuncao.lower() not in acao.lower() else ''}
          &nbsp;<span style="color:#94a3b8">· {ano}</span>
          &nbsp;{_badge(status)}
        </div>
      </div>
      <div class="rep-val">{_R(recebido)}</div>
    </div>"""

        html += "\n  </div>\n</div>"

    return html


def _tabela_ano(anos: list) -> str:
    linhas = ""
    for r in anos:
        emp = r.get("empenhado") or 0
        rec = r.get("recebido") or 0
        restos = r.get("restos_inscritos") or 0
        linhas += (
            f"<tr>"
            f"<td style='font-weight:800'>{r['ano']}</td>"
            f"<td style='text-align:center'>{r['emendas']}</td>"
            f"<td style='text-align:right'>{_R(emp)}</td>"
            f"<td style='text-align:right;color:#10b981;font-weight:700'>{_R(rec)}</td>"
            f"<td style='text-align:right;color:#f59e0b'>{_R(restos) if restos > 0 else '—'}</td>"
            f"<td>{_barra(rec, emp)}</td>"
            f"</tr>"
        )
    return linhas


def _tabela_categorias(cats: list) -> str:
    linhas = ""
    for r in cats:
        linhas += (
            f"<tr>"
            f"<td>{_badge_cat(r['categoria'])}</td>"
            f"<td style='text-align:center'>{r['emendas']}</td>"
            f"<td style='text-align:right'>{_R(r['empenhado'])}</td>"
            f"<td style='text-align:right;color:#10b981'>{_R(r['pago'])}</td>"
            f"<td>{_barra(r['pago'], r['empenhado'])}</td>"
            f"</tr>"
        )
    return linhas


def _badge_situacao(s: str) -> str:
    s = (s or "").upper()
    if "NORMAL" in s or "CONCLUÍDO" in s:
        return f'<span style="background:#d1fae5;color:#065f46;padding:2px 7px;border-radius:8px;font-size:9px;font-weight:700">{s.title()}</span>'
    if "EXECUÇÃO" in s:
        return f'<span style="background:#dbeafe;color:#1e40af;padding:2px 7px;border-radius:8px;font-size:9px;font-weight:700">Em execução</span>'
    if "CONTAS" in s:
        return f'<span style="background:#fef3c7;color:#92400e;padding:2px 7px;border-radius:8px;font-size:9px;font-weight:700">Prest. contas</span>'
    if s:
        return f'<span style="background:#f3f4f6;color:#374151;padding:2px 7px;border-radius:8px;font-size:9px;font-weight:700">{s.title()}</span>'
    return ""


def _tabela_convenios(convenios: list) -> str:
    if not convenios:
        return "<tr><td colspan='5' style='text-align:center;color:#9ca3af;padding:20px'>Nenhum convênio encontrado</td></tr>"
    linhas = ""
    for c in convenios:
        municipio = c.get("municipio") or c.get("localidade") or "Bahia"
        uf = c.get("uf") or "BA"
        objeto = c.get("objeto") or "—"
        convenente = (c.get("convenente") or "—").title()
        cat = c.get("categoria") or "Outros"
        ano = c.get("ano") or "—"

        # Dados enriquecidos da API
        ministerio = c.get("ministerio") or ""
        ministerio_curto = ministerio.replace(" - Unidades com vínculo direto", "").replace("Ministério d", "Min. d")
        unidade = c.get("unidade_gestora") or ""
        situacao = c.get("situacao_api") or c.get("status") or ""
        valor_conv = c.get("valor") or 0
        valor_lib = c.get("valor_liberado") or 0
        contrapartida = c.get("valor_contrapartida") or 0
        dt_inicio = (c.get("dt_inicio_vigencia") or "")[:10]
        dt_fim = (c.get("dt_fim_vigencia") or "")[:10]
        num_processo = c.get("numero_processo") or ""

        pct_lib = (valor_lib / valor_conv * 100) if valor_conv else 0
        cor_lib = "#10b981" if pct_lib >= 90 else ("#f59e0b" if pct_lib >= 40 else "#ef4444")

        linhas += f"""
<tr>
  <td style="padding:12px 10px">
    <div style="font-weight:800;color:#003DA5;font-size:12px">{municipio}/{uf}</div>
    <div style="font-size:11px;color:#374151;margin-top:2px">{convenente}</div>
    {f'<div style="font-size:10px;color:#94a3b8;margin-top:2px">Processo: {num_processo}</div>' if num_processo else ''}
  </td>
  <td style="padding:12px 10px">
    <div style="font-size:12px;color:#1e293b;font-weight:600;line-height:1.4">{objeto}</div>
    {f'<div style="font-size:10px;color:#6b7280;margin-top:3px">📌 {ministerio_curto}</div>' if ministerio_curto else ''}
    {f'<div style="font-size:10px;color:#94a3b8">{unidade[:60]}</div>' if unidade else ''}
    <div style="margin-top:4px;display:flex;gap:4px;flex-wrap:wrap">
      {_badge_cat(cat)}
      {_badge_situacao(situacao)}
    </div>
  </td>
  <td style="padding:12px 10px;text-align:center;font-size:11px;color:#64748b;white-space:nowrap">
    {ano}<br>
    {f'<span style="font-size:10px">{dt_inicio}</span><br><span style="font-size:10px;color:#94a3b8">até {dt_fim}</span>' if dt_inicio else ''}
  </td>
  <td style="padding:12px 10px;text-align:right">
    <div style="font-size:13px;font-weight:800;color:#003DA5">{_R(valor_conv)}</div>
    <div style="font-size:10px;color:#64748b;margin-top:2px">contratado</div>
    {f'<div style="font-size:12px;font-weight:700;color:{cor_lib};margin-top:3px">{_R(valor_lib)} liberado</div>' if valor_lib else ''}
    {f'<div style="font-size:10px;color:#94a3b8">+ {_R(contrapartida)} contrapartida mun.</div>' if contrapartida > 0 else ''}
    {f'<div style="margin-top:4px;background:#e5e7eb;border-radius:3px;height:5px;width:80px"><div style="background:{cor_lib};height:5px;border-radius:3px;width:{min(pct_lib,100):.0f}%"></div></div>' if valor_conv else ''}
  </td>
</tr>"""
    return linhas


def gerar_html(resumo: dict, alertas: list) -> str:
    t = resumo.get("totais") or {}
    total_e = t.get("total_empenhado") or 0
    total_rec = t.get("total_recebido") or 0
    total_pix = t.get("total_pix") or 0
    total_mun = t.get("total_municipios") or 0
    total_qt = t.get("total_emendas") or 0
    total_geral = total_rec + total_pix
    conv_qt = len(resumo.get("convenios") or [])
    municipios_det = resumo.get("municipios_detalhados") or []
    nome_parlamentar = PARLAMENTAR.title()

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Emendas {nome_parlamentar} — {datetime.now().strftime('%m/%Y')}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <h1>📊 Monitor de Emendas Parlamentares — Dep. {nome_parlamentar}</h1>
  <p>Bahia · Dados do Portal da Transparência (CGU) · Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="kv">{total_qt}</div><div class="kl">Emendas únicas</div></div>
  <div class="kpi"><div class="kv">{_Rm(total_e)}</div><div class="kl">Total empenhado</div></div>
  <div class="kpi"><div class="kv">{_Rm(total_geral)}</div><div class="kl">Efetivamente entregue</div></div>
  <div class="kpi"><div class="kv">{total_mun}+ municípios</div><div class="kl">Beneficiados (BA)</div></div>
</div>

<div style="padding:0 36px 0">
  <div class="nota" style="margin-top:16px">
    <strong>Como ler os valores:</strong>
    Convênios com destino definido: <strong>{_Rm(total_rec)}</strong> entregues diretamente a municípios e entidades da Bahia.
    Transferências Especiais (PIX): <strong>{_Rm(total_pix)}</strong> distribuídas ao estado sem destinação específica prévia.
    Total efetivamente entregue: <strong>{_Rm(total_geral)}</strong> de {_Rm(total_e)} empenhados.
  </div>
</div>

{_secao_alertas(alertas)}

<div class="sec">
  <h2>📍 Municípios Atendidos — {total_mun} municípios da Bahia</h2>
  <p style="font-size:11px;color:#6b7280;margin-bottom:16px">
    Para cada município: quem recebeu o recurso, qual foi o objetivo da emenda e o valor exato entregue.
  </p>
  {_secao_municipios(municipios_det)}
</div>

<div class="sec">
  <h2>📋 Todas as Emendas — Explicação Completa por Ano</h2>
  <p style="font-size:11px;color:#6b7280;margin-bottom:16px">
    Cada emenda com seu objetivo, área de atuação, município beneficiado e situação atual.
  </p>
  {_secao_emendas(resumo.get("todas_emendas") or [])}
</div>

{f'''<div class="sec">
  <h2>📄 Convênios Registrados ({conv_qt})</h2>
  <p style="font-size:11px;color:#6b7280;margin-bottom:12px">Objeto exato de cada convênio no SICONV/Transferegov.</p>
  <div style="overflow-x:auto">
  <table>
    <tr>
      <th>Município / Beneficiário</th>
      <th>Objeto · Ministério · Situação</th>
      <th style="text-align:center">Ano / Vigência</th>
      <th style="text-align:right">Valores</th>
    </tr>
    {_tabela_convenios(resumo.get("convenios") or [])}
  </table>
  </div>
</div>''' if conv_qt > 0 else ''}

<div class="sec">
  <h2>📅 Histórico Anual</h2>
  <p style="font-size:11px;color:#6b7280;margin-bottom:10px">
    Empenhado = comprometimento do orçamento. Entregue = repasses reais (inclui Restos a Pagar de anos anteriores).
  </p>
  <table>
    <tr>
      <th>Ano</th><th style="text-align:center">Emendas</th>
      <th style="text-align:right">Empenhado</th>
      <th style="text-align:right">Efetivamente entregue</th>
      <th style="text-align:right">A pagar</th><th>Execução</th>
    </tr>
    {_tabela_ano(resumo.get("por_ano") or [])}
  </table>
</div>

<div class="sec">
  <h2>🏷 Por Área de Atuação</h2>
  <table>
    <tr><th>Área</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th>
        <th style="text-align:right">Pago</th><th>Execução</th></tr>
    {_tabela_categorias(resumo.get("por_categoria") or [])}
  </table>
</div>

<div class="sec">
  <h2>⚙️ Por Status</h2>
  <table>
    <tr><th>Status</th><th style="text-align:center">Emendas</th>
        <th style="text-align:right">Empenhado</th><th style="text-align:right">Pago</th></tr>
    {"".join(
        f"<tr><td>{_badge(r['status'])}</td><td style='text-align:center'>{r['emendas']}</td>"
        f"<td style='text-align:right'>{_R(r['empenhado'])}</td>"
        f"<td style='text-align:right'>{_R(r['pago'])}</td></tr>"
        for r in (resumo.get("por_status") or [])
    )}
  </table>
</div>

<div class="footer">
  Monitor de Emendas Parlamentares · Dep. {nome_parlamentar} (BA) · Código do autor: {CODIGO_AUTOR}<br>
  Fonte: Portal da Transparência do Governo Federal — portaldatransparencia.gov.br<br>
  {datetime.now().strftime('%d/%m/%Y %H:%M')}
</div>

</div>
</body>
</html>"""


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
    nome_parl = PARLAMENTAR.title()
    mes = datetime.now().strftime("%B/%Y")
    assunto = f"Emendas {nome_parl} — Relatório {mes}"

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
