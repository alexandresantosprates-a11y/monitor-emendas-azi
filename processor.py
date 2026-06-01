from __future__ import annotations

import logging
from typing import Dict, List, Tuple

from categorias import categorizar
import database as db

logger = logging.getLogger(__name__)


def _float(v) -> float:
    if not v:
        return 0.0
    try:
        return float(str(v).strip().replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return 0.0


def _str(v) -> str:
    return str(v).strip() if v else ""


def _status(emp: float, liq: float, pago: float) -> str:
    if pago > 0:
        return "PAGO"
    if liq > 0:
        return "LIQUIDADO"
    if emp > 0:
        return "EMPENHADO"
    return "AUTORIZADO"


def _municipio_uf(localidade: str) -> Tuple[str, str]:
    """Extrai município e UF de strings como 'ALAGOINHAS - BA'."""
    loc = _str(localidade)
    if " - " in loc:
        partes = loc.rsplit(" - ", 1)
        return partes[0].strip().title(), partes[1].strip()
    if loc.endswith("(UF)") or loc.upper() == "MÚLTIPLO":
        return "", "BA"
    return loc.title(), "BA"


# ---------------------------------------------------------------------------
# Processar CSV de emendas (EmendasParlamentares.csv)
# ---------------------------------------------------------------------------

def processar_emendas_csv(rows: List[Dict]) -> int:
    ok = 0
    for r in rows:
        try:
            codigo = _str(r.get("Código da Emenda") or "")
            ano_str = _str(r.get("Ano da Emenda") or "")
            if not codigo or not ano_str:
                continue

            localidade = _str(r.get("Localidade de aplicação do recurso") or "")
            municipio_raw = _str(r.get("Município") or "")
            uf_raw = _str(r.get("UF") or "")

            # Municipio específico ou extraído da localidade
            if municipio_raw and municipio_raw.lower() != "múltiplo":
                municipio = municipio_raw.title()
                uf = uf_raw[:2] if uf_raw else "BA"
            else:
                municipio, uf = _municipio_uf(localidade)

            subfuncao = _str(r.get("Nome Subfunção") or "")
            funcao = _str(r.get("Nome Função") or "")
            funcao_cod = _str(r.get("Código Função") or "")
            categoria = categorizar(funcao_cod, subfuncao or funcao)

            emp = _float(r.get("Valor Empenhado"))
            liq = _float(r.get("Valor Liquidado"))
            pago = _float(r.get("Valor Pago"))
            restos_i = _float(r.get("Valor Restos A Pagar Inscritos"))
            restos_p = _float(r.get("Valor Restos A Pagar Pagos"))

            # ID único: código da emenda + municipio (pode ter uma emenda em vários municípios)
            id_row = f"{codigo}-{municipio or localidade}".replace(" ", "_")

            emenda = {
                "id": id_row,
                "codigo": codigo,
                "ano": int(ano_str),
                "tipo": _str(r.get("Tipo de Emenda") or ""),
                "autor": _str(r.get("Nome do Autor da Emenda") or "PAULO AZI"),
                "numero": _str(r.get("Número da emenda") or ""),
                "localidade": localidade,
                "municipio_ibge": _str(r.get("Código Município IBGE") or ""),
                "municipio": municipio,
                "uf": uf,
                "regiao": _str(r.get("Região") or ""),
                "funcao": funcao,
                "subfuncao": subfuncao,
                "programa": _str(r.get("Nome Programa") or ""),
                "acao": _str(r.get("Nome Ação") or ""),
                "plano_orcamentario": _str(r.get("Nome Plano Orçamentário") or ""),
                "categoria": categoria,
                "valor_empenhado": emp,
                "valor_liquidado": liq,
                "valor_pago": pago,
                "valor_restos_inscritos": restos_i,
                "valor_restos_pagos": restos_p,
                "status": _status(emp, liq, pago),
            }

            db.upsert_emenda(emenda)
            ok += 1

        except Exception as e:
            logger.error("Erro emenda CSV: %s | %s", e, r)

    return ok


# ---------------------------------------------------------------------------
# Processar CSV de convênios (EmendasParlamentares_Convenios.csv)
# ---------------------------------------------------------------------------

def processar_convenios_csv(rows: List[Dict]) -> int:
    ok = 0
    for r in rows:
        try:
            codigo_emenda = _str(r.get("Código da Emenda") or "")
            numero = _str(r.get("Número Convênio") or "")
            if not codigo_emenda:
                continue

            localidade = _str(r.get("Localidade do gasto") or "")
            municipio, uf = _municipio_uf(localidade)

            funcao = _str(r.get("Nome Função") or "")
            subfuncao = _str(r.get("Nome Subfunção") or "")
            funcao_cod = _str(r.get("Código Função") or "")
            objeto = _str(r.get("Objeto Convênio") or "")
            categoria = categorizar(funcao_cod, objeto or subfuncao or funcao)

            conv_id = f"{codigo_emenda}-{numero or localidade}".replace(" ", "_")

            convenio = {
                "id": conv_id,
                "codigo_emenda": codigo_emenda,
                "funcao": funcao,
                "subfuncao": subfuncao,
                "localidade": localidade,
                "tipo_emenda": _str(r.get("Tipo de Emenda") or ""),
                "data_publicacao": _str(r.get("Data Publicação Convênio") or ""),
                "convenente": _str(r.get("Convenente") or ""),
                "objeto": objeto,
                "numero": numero,
                "valor": _float(r.get("Valor Convênio") or 0),
                "categoria": categoria,
                "municipio": municipio,
                "uf": uf,
            }

            db.upsert_convenio(convenio)
            ok += 1

        except Exception as e:
            logger.error("Erro convênio CSV: %s | %s", e, r)

    return ok
