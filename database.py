import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "emendas.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar():
    conn = get_connection()
    c = conn.cursor()

    # Emendas detalhadas (uma linha por emenda + município + ação)
    c.execute("""
        CREATE TABLE IF NOT EXISTS emendas (
            id TEXT PRIMARY KEY,
            codigo TEXT,
            ano INTEGER,
            tipo TEXT,
            autor TEXT,
            numero TEXT,
            localidade TEXT,
            municipio_ibge TEXT,
            municipio TEXT,
            uf TEXT,
            regiao TEXT,
            funcao TEXT,
            subfuncao TEXT,
            programa TEXT,
            acao TEXT,
            plano_orcamentario TEXT,
            categoria TEXT,
            valor_empenhado REAL DEFAULT 0,
            valor_liquidado REAL DEFAULT 0,
            valor_pago REAL DEFAULT 0,
            valor_restos_inscritos REAL DEFAULT 0,
            valor_restos_pagos REAL DEFAULT 0,
            status TEXT,
            atualizado_em TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Convênios com objeto exato e município
    c.execute("""
        CREATE TABLE IF NOT EXISTS convenios (
            id TEXT PRIMARY KEY,
            codigo_emenda TEXT,
            funcao TEXT,
            subfuncao TEXT,
            localidade TEXT,
            tipo_emenda TEXT,
            data_publicacao TEXT,
            convenente TEXT,
            objeto TEXT,
            numero TEXT,
            valor REAL DEFAULT 0,
            categoria TEXT,
            municipio TEXT,
            uf TEXT,
            atualizado_em TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Alertas de mudanças detectadas
    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT,
            referencia_id TEXT,
            descricao TEXT,
            valor REAL DEFAULT 0,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
            enviado INTEGER DEFAULT 0
        )
    """)

    # Registro de coletas
    c.execute("""
        CREATE TABLE IF NOT EXISTS coletas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte TEXT,
            total_registros INTEGER,
            status TEXT,
            erro TEXT,
            executado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def upsert_emenda(d: dict):
    conn = get_connection()
    c = conn.cursor()
    agora = datetime.now().isoformat()

    c.execute("SELECT valor_pago, status FROM emendas WHERE id = ?", (d["id"],))
    anterior = c.fetchone()

    c.execute("""
        INSERT INTO emendas (id, codigo, ano, tipo, autor, numero, localidade,
            municipio_ibge, municipio, uf, regiao, funcao, subfuncao, programa, acao,
            plano_orcamentario, categoria, valor_empenhado, valor_liquidado, valor_pago,
            valor_restos_inscritos, valor_restos_pagos, status, atualizado_em)
        VALUES (:id,:codigo,:ano,:tipo,:autor,:numero,:localidade,:municipio_ibge,
            :municipio,:uf,:regiao,:funcao,:subfuncao,:programa,:acao,:plano_orcamentario,
            :categoria,:valor_empenhado,:valor_liquidado,:valor_pago,
            :valor_restos_inscritos,:valor_restos_pagos,:status,:atualizado_em)
        ON CONFLICT(id) DO UPDATE SET
            valor_empenhado=excluded.valor_empenhado,
            valor_liquidado=excluded.valor_liquidado,
            valor_pago=excluded.valor_pago,
            valor_restos_inscritos=excluded.valor_restos_inscritos,
            valor_restos_pagos=excluded.valor_restos_pagos,
            status=excluded.status,
            programa=excluded.programa,
            acao=excluded.acao,
            atualizado_em=excluded.atualizado_em
    """, {**d, "atualizado_em": agora})

    if anterior:
        delta_pago = (d.get("valor_pago") or 0) - (anterior["valor_pago"] or 0)
        if delta_pago > 100:
            c.execute("""
                INSERT INTO alertas (tipo, referencia_id, descricao, valor, criado_em)
                VALUES (?,?,?,?,?)
            """, ("NOVO_PAGAMENTO", d["id"],
                  f"Pagamento de R$ {delta_pago:,.2f} na emenda {d['numero']} "
                  f"({d['categoria']}) — {d.get('municipio') or d.get('localidade') or 'Bahia'}",
                  delta_pago, agora))
        if anterior["status"] != d.get("status"):
            c.execute("""
                INSERT INTO alertas (tipo, referencia_id, descricao, valor, criado_em)
                VALUES (?,?,?,?,?)
            """, ("MUDANCA_STATUS", d["id"],
                  f"Emenda {d['numero']} mudou de {anterior['status']} para {d['status']} "
                  f"({d.get('municipio') or d.get('localidade') or 'Bahia'}) "
                  f"— {d['categoria']}",
                  d.get("valor_empenhado", 0), agora))

    conn.commit()
    conn.close()


def upsert_convenio(d: dict):
    conn = get_connection()
    c = conn.cursor()
    agora = datetime.now().isoformat()
    c.execute("""
        INSERT INTO convenios (id, codigo_emenda, funcao, subfuncao, localidade, tipo_emenda,
            data_publicacao, convenente, objeto, numero, valor, categoria, municipio, uf, atualizado_em)
        VALUES (:id,:codigo_emenda,:funcao,:subfuncao,:localidade,:tipo_emenda,
            :data_publicacao,:convenente,:objeto,:numero,:valor,:categoria,:municipio,:uf,:atualizado_em)
        ON CONFLICT(id) DO UPDATE SET
            valor=excluded.valor,
            objeto=excluded.objeto,
            atualizado_em=excluded.atualizado_em
    """, {**d, "atualizado_em": agora})
    conn.commit()
    conn.close()


def registrar_coleta(fonte: str, total: int, status: str, erro: str = None):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO coletas (fonte, total_registros, status, erro) VALUES (?,?,?,?)",
              (fonte, total, status, erro))
    conn.commit()
    conn.close()


def buscar_alertas_nao_enviados() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM alertas WHERE enviado=0 ORDER BY criado_em DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def marcar_alertas_enviados(ids: list):
    if not ids:
        return
    conn = get_connection()
    c = conn.cursor()
    placeholders = ",".join("?" * len(ids))
    c.execute(f"UPDATE alertas SET enviado=1 WHERE id IN ({placeholders})", ids)
    conn.commit()
    conn.close()


def resumo_completo() -> dict:
    conn = get_connection()
    c = conn.cursor()

    # Totais gerais
    c.execute("""
        SELECT COUNT(DISTINCT codigo) as total_emendas,
               SUM(valor_empenhado) as total_empenhado,
               SUM(valor_liquidado) as total_liquidado,
               SUM(valor_pago) as total_pago,
               SUM(valor_restos_inscritos) as total_a_pagar
        FROM emendas
    """)
    totais = dict(c.fetchone())

    # Por categoria/área
    c.execute("""
        SELECT categoria,
               COUNT(DISTINCT codigo) as emendas,
               SUM(valor_empenhado) as empenhado,
               SUM(valor_pago) as pago
        FROM emendas
        GROUP BY categoria ORDER BY empenhado DESC
    """)
    por_categoria = [dict(r) for r in c.fetchall()]

    # Por status
    c.execute("""
        SELECT status, COUNT(DISTINCT codigo) as emendas,
               SUM(valor_empenhado) as empenhado, SUM(valor_pago) as pago
        FROM emendas GROUP BY status ORDER BY empenhado DESC
    """)
    por_status = [dict(r) for r in c.fetchall()]

    # Por ano
    c.execute("""
        SELECT ano,
               COUNT(DISTINCT codigo) as emendas,
               SUM(valor_empenhado) as empenhado,
               SUM(valor_liquidado) as liquidado,
               SUM(valor_pago) as pago
        FROM emendas GROUP BY ano ORDER BY ano DESC
    """)
    por_ano = [dict(r) for r in c.fetchall()]

    # Top municípios beneficiados (via tabela emendas com município específico)
    c.execute("""
        SELECT municipio, uf,
               COUNT(DISTINCT codigo) as emendas,
               SUM(valor_empenhado) as empenhado,
               SUM(valor_pago) as pago
        FROM emendas
        WHERE municipio IS NOT NULL AND municipio != '' AND municipio != 'Múltiplo'
        GROUP BY municipio, uf
        ORDER BY empenhado DESC LIMIT 25
    """)
    top_municipios = [dict(r) for r in c.fetchall()]

    # Convênios — lista completa por área
    c.execute("""
        SELECT c.*, e.ano, e.status, e.valor_pago as valor_pago_emenda
        FROM convenios c
        LEFT JOIN (
            SELECT codigo, MAX(ano) as ano, MAX(status) as status, SUM(valor_pago) as valor_pago
            FROM emendas GROUP BY codigo
        ) e ON c.codigo_emenda = e.codigo
        ORDER BY c.municipio, c.data_publicacao DESC
    """)
    convenios = [dict(r) for r in c.fetchall()]

    # Lista de todas emendas por ano/área para tabela detalhada
    c.execute("""
        SELECT *, ROW_NUMBER() OVER (PARTITION BY codigo ORDER BY valor_empenhado DESC) as rn
        FROM emendas
    """)
    todas = [dict(r) for r in c.fetchall()]

    conn.close()

    return {
        "totais": totais,
        "por_categoria": por_categoria,
        "por_status": por_status,
        "por_ano": por_ano,
        "top_municipios": top_municipios,
        "convenios": convenios,
        "todas_emendas": todas,
    }
