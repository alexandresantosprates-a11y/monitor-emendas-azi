"""
Coleta de dados do Portal da Transparência via:
  1. API oficial (/emendas) — valores atualizados diariamente
  2. CSV dados abertos — detalhes: município, objeto convênio, ação orçamentária
"""

from __future__ import annotations

import io
import os
import time
import zipfile
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

BASE_API = "https://api.portaldatransparencia.gov.br/api-de-dados"
URL_ZIP_BASE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/emendas-parlamentares"

CODIGO_AUTOR_AZI = "3738"
ANO_INICIO = 2016


def _headers_api() -> dict:
    chave = os.getenv("TRANSPARENCIA_API_KEY", "")
    return {"chave-api-dados": chave, "Accept": "application/json"}


def _headers_web() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    }


# ---------------------------------------------------------------------------
# API oficial — valores financeiros atualizados
# ---------------------------------------------------------------------------

def enriquecer_convenios_api(numeros: List[str]) -> Dict:
    """Busca dados extras de cada convênio: ministério, valor liberado, datas, situação."""
    resultado = {}
    for num in numeros:
        if not num or not num.strip().isdigit():
            continue
        try:
            r = requests.get(
                f"{BASE_API}/convenios",
                headers=_headers_api(),
                params={"numero": num.strip(), "pagina": 1, "tamanhoDaPagina": 1},
                timeout=30,
            )
            if r.status_code == 200:
                dados = r.json()
                if isinstance(dados, list) and dados:
                    d = dados[0]
                    resultado[num.strip()] = {
                        "ministerio": d.get("orgao", {}).get("nome", ""),
                        "unidade_gestora": d.get("unidadeGestora", {}).get("nome", ""),
                        "situacao_api": d.get("situacao", ""),
                        "valor_liberado": d.get("valorLiberado") or 0,
                        "valor_contrapartida": d.get("valorContrapartida") or 0,
                        "dt_inicio_vigencia": d.get("dataInicioVigencia", ""),
                        "dt_fim_vigencia": d.get("dataFinalVigencia", ""),
                        "dt_ultima_liberacao": d.get("dataUltimaLiberacao", ""),
                        "numero_processo": d.get("numeroProcesso", ""),
                        "cnpj_convenente": d.get("convenente", {}).get("cnpjFormatado", ""),
                    }
            time.sleep(0.3)
        except Exception as e:
            logger.warning("Enriquecimento convênio %s: %s", num, e)
    logger.info("Convênios enriquecidos: %d", len(resultado))
    return resultado


def buscar_emendas_api(nome_parlamentar: str, ano: int) -> List[Dict]:
    params = {
        "nomeAutor": nome_parlamentar,
        "ano": ano,
        "pagina": 1,
        "tamanhoDaPagina": 500,
    }
    for tentativa in range(3):
        try:
            r = requests.get(f"{BASE_API}/emendas", headers=_headers_api(),
                             params=params, timeout=30)
            if r.status_code == 200:
                dados = r.json()
                return dados if isinstance(dados, list) else []
            time.sleep(3 * (tentativa + 1))
        except Exception as e:
            logger.warning("API emendas %d tentativa %d: %s", ano, tentativa + 1, e)
    return []


# ---------------------------------------------------------------------------
# CSV dados abertos — município + objeto + ação orçamentária
# ---------------------------------------------------------------------------

def _baixar_zip() -> Optional[zipfile.ZipFile]:
    """Baixa o ZIP único que contém todos os anos."""
    url = f"{URL_ZIP_BASE}/EmendasParlamentares.zip"
    logger.info("Baixando CSV dados abertos: %s", url)
    for tentativa in range(3):
        try:
            r = requests.get(url, headers=_headers_web(), stream=True, timeout=300)
            r.raise_for_status()
            return zipfile.ZipFile(io.BytesIO(r.content))
        except Exception as e:
            logger.warning("Download ZIP tentativa %d: %s", tentativa + 1, e)
            time.sleep(10)
    return None


def _parse_csv(conteudo: str) -> Tuple[List[str], List[List[str]]]:
    linhas = conteudo.split("\n")
    header = [c.strip().strip('"') for c in linhas[0].split(";")]
    rows = []
    for l in linhas[1:]:
        if not l.strip():
            continue
        campos = [v.strip().strip('"') for v in l.split(";")]
        if len(campos) >= len(header) - 2:
            rows.append(campos)
    return header, rows


def _row_to_dict(header: List[str], row: List[str]) -> Dict:
    return {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}


def carregar_csv_detalhado() -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Retorna (emendas_azi, convenios_azi, favorecidos_azi) com todos os dados do CSV.
    Filtra automaticamente pelo código do autor Paulo Azi (3738).
    """
    z = _baixar_zip()
    if not z:
        logger.error("Não foi possível baixar o ZIP de dados abertos.")
        return [], [], []

    # CSV principal: emendas por linha de execução (município + ação)
    raw_principal = z.read("EmendasParlamentares.csv").decode("latin-1")
    header_p, rows_p = _parse_csv(raw_principal)
    emendas = []
    for row in rows_p:
        d = _row_to_dict(header_p, row)
        if d.get("Código do Autor da Emenda", "").strip() == CODIGO_AUTOR_AZI:
            emendas.append(d)

    codigos_azi = {e["Código da Emenda"] for e in emendas}

    # CSV de convênios: objeto exato + convenente + município
    raw_conv = z.read("EmendasParlamentares_Convenios.csv").decode("latin-1")
    header_c, rows_c = _parse_csv(raw_conv)
    convenios = []
    for row in rows_c:
        d = _row_to_dict(header_c, row)
        if d.get("Código da Emenda", "") in codigos_azi:
            convenios.append(d)

    # CSV por favorecido: pagamentos reais por entidade/município
    raw_fav = z.read("EmendasParlamentares_PorFavorecido.csv").decode("latin-1")
    header_f, rows_f = _parse_csv(raw_fav)
    favorecidos = []
    for row in rows_f:
        d = _row_to_dict(header_f, row)
        if d.get("Código do Autor da Emenda", "").strip() == CODIGO_AUTOR_AZI:
            favorecidos.append(d)

    logger.info("CSV carregado: %d emendas, %d convênios, %d favorecidos de Paulo Azi",
                len(emendas), len(convenios), len(favorecidos))
    return emendas, convenios, favorecidos
