"""
Monitor de Emendas Parlamentares — Paulo Azi

  python main.py historico       — coleta completa (API + CSV dados abertos)
  python main.py coletar         — atualização rápida via API
  python main.py relatorio       — envia relatório por e-mail
  python main.py relatorio --local — salva HTML sem enviar
  python main.py resumo          — exibe resumo no terminal
  python main.py monitor         — daemon contínuo
"""

import os, sys, logging, schedule, time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import database as db
import fetcher
import processor
import emailer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "monitor.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("monitor")

PARLAMENTAR = os.getenv("PARLAMENTAR_NOME", "PAULO AZI")


def coletar_completo():
    """Coleta completa: CSV dados abertos (município + objeto) + API (valores atuais)."""
    logger.info("=== COLETA COMPLETA ===")

    # 1. CSV dados abertos — município, objeto, ação, favorecidos
    logger.info("Baixando CSV dados abertos (todos os anos)...")
    emendas_csv, convenios_csv, favorecidos_csv = fetcher.carregar_csv_detalhado()
    ok_e = processor.processar_emendas_csv(emendas_csv)
    ok_c = processor.processar_convenios_csv(convenios_csv)
    ok_f = processor.processar_favorecidos_csv(favorecidos_csv)
    db.registrar_coleta("csv_emendas", ok_e, "OK")
    db.registrar_coleta("csv_convenios", ok_c, "OK")
    db.registrar_coleta("csv_favorecidos", ok_f, "OK")
    logger.info("CSV: %d emendas, %d convênios, %d favorecidos salvos", ok_e, ok_c, ok_f)

    # 2. Enriquece convênios com dados da API (ministério, valor liberado, datas)
    logger.info("Enriquecendo convênios com dados da API...")
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT numero FROM convenios WHERE numero != '' AND numero GLOB '[0-9]*'")
    numeros = [r["numero"] for r in cur.fetchall()]
    conn.close()
    enriquecidos = fetcher.enriquecer_convenios_api(numeros)
    for num, dados in enriquecidos.items():
        db.enriquecer_convenio(num, dados)
    logger.info("Convênios enriquecidos: %d", len(enriquecidos))

    # 3. API — atualizar valores financeiros recentes (últimos 3 anos)
    logger.info("Atualizando valores via API...")
    ano_atual = datetime.now().year
    for ano in range(ano_atual - 2, ano_atual + 1):
        raw = fetcher.buscar_emendas_api(PARLAMENTAR, ano)
        for r in raw:
            codigo = str(r.get("codigoEmenda") or "")
            emp = _float_api(r.get("valorEmpenhado"))
            liq = _float_api(r.get("valorLiquidado"))
            pago = _float_api(r.get("valorPago"))
            if not codigo:
                continue
            # Atualizar registros existentes com os valores mais recentes
            _atualizar_valores_api(codigo, emp, liq, pago)
        time.sleep(0.5)

    logger.info("=== COLETA COMPLETA CONCLUÍDA ===")


def _float_api(v) -> float:
    if not v:
        return 0.0
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except:
        return 0.0


def _atualizar_valores_api(codigo: str, emp: float, liq: float, pago: float):
    """Atualiza valores financeiros dos registros de uma emenda via API."""
    import sqlite3
    conn = db.get_connection()
    c = conn.cursor()
    agora = datetime.now().isoformat()
    status = "PAGO" if pago > 0 else ("LIQUIDADO" if liq > 0 else "EMPENHADO")
    c.execute("""
        UPDATE emendas SET
            valor_empenhado=?, valor_liquidado=?, valor_pago=?, status=?, atualizado_em=?
        WHERE codigo=?
    """, (emp, liq, pago, status, agora, codigo))
    conn.commit()
    conn.close()


def enviar_relatorio(local_only: bool = False):
    resumo = db.resumo_completo()
    alertas = db.buscar_alertas_nao_enviados()
    if local_only:
        caminho = emailer.salvar_html_local(resumo, alertas)
        print(f"\nRelatório salvo: {caminho}")
        return
    sucesso = emailer.enviar_relatorio(resumo, alertas)
    if sucesso:
        db.marcar_alertas_enviados([a["id"] for a in alertas])


def imprimir_resumo():
    resumo = db.resumo_completo()
    t = resumo["totais"]
    print("\n" + "=" * 65)
    print(f"  EMENDAS PARLAMENTARES — {PARLAMENTAR}")
    print("=" * 65)
    print(f"  Total de emendas (únicas):  {t['total_emendas']}")
    print(f"  Total empenhado:   R$ {t['total_empenhado']:>18,.2f}")
    print(f"  Total pago:        R$ {t['total_pago']:>18,.2f}")
    print(f"  A pagar:           R$ {t['total_a_pagar']:>18,.2f}")
    print("\n  Por área:")
    for r in resumo["por_categoria"]:
        pct = (r["pago"] / r["empenhado"] * 100) if r["empenhado"] else 0
        print(f"    {r['categoria']:25s} {r['emendas']:2d} emendas  "
              f"R${r['empenhado']:>15,.2f}  pago {pct:.0f}%")
    print("\n  Top 10 municípios (por valor recebido):")
    for r in resumo["top_municipios"][:10]:
        print(f"    {r['municipio']}/{r.get('uf','BA'):2s}  R${r.get('recebido', r.get('empenhado',0)):>15,.2f}")
    print("\n  Convênios com objeto detalhado:", len(resumo["convenios"]))
    print("=" * 65 + "\n")


def iniciar_monitor():
    logger.info("=== DAEMON INICIADO ===")
    schedule.every().day.at("06:00").do(coletar_completo)
    schedule.every(5).days.do(lambda: enviar_relatorio())
    schedule.every().month.do(lambda: enviar_relatorio())
    coletar_completo()
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Monitor encerrado.")


if __name__ == "__main__":
    db.inicializar()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "resumo"
    if cmd == "historico":
        coletar_completo()
        imprimir_resumo()
    elif cmd == "coletar":
        coletar_completo()
        imprimir_resumo()
    elif cmd == "relatorio":
        enviar_relatorio(local_only="--local" in sys.argv)
    elif cmd == "resumo":
        imprimir_resumo()
    elif cmd == "monitor":
        iniciar_monitor()
    else:
        print(__doc__)
        sys.exit(1)
