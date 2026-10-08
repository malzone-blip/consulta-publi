# -*- coding: utf-8 -*-
"""Classificacoes fiscais e dados societarios.

  Siscomex / Portal Unico -> NCM e Tarifa Externa Comum (publico, sem chave)
  IBGE                    -> CNAE (secoes, divisoes, classes)
  CVM                     -> cadastro de companhias abertas (CSV publico)
"""
import io
import re
import time
import zipfile

import pandas as pd
import streamlit as st

from core import http
from core.config import DIR_CACHE, TTL_CADASTRAL, TTL_MEMORIA, TTL_MENSAL

NCM_SISCOMEX = ("https://portalunico.siscomex.gov.br/classif/api/publico/"
                "nomenclatura/download/json")
CNAE_IBGE = "https://servicodados.ibge.gov.br/api/v2/cnae"
CVM_CADASTRO = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
CVM_FUNDOS_CAD = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
CVM_FUNDOS_INF = ("https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
                  "inf_diario_fi_%s.zip")


# ---------------------------------------------------------------------------
# NCM / Tarifa Externa Comum
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ncm(forcar: bool = False):
    """Nomenclatura Comum do Mercosul completa, com vigencia e ato legal."""
    resp = http.obter_json(NCM_SISCOMEX, TTL_CADASTRAL, "Siscomex/NCM-TEC", forcar,
                           timeout=90)
    if not resp.ok:
        return pd.DataFrame(), resp, ""
    bruto = resp.dados
    atualizacao = ""
    lista = bruto
    if isinstance(bruto, dict):
        atualizacao = bruto.get("Data_Ultima_Atualizacao_NCM", "")
        for k in ("Nomenclaturas", "nomenclaturas", "value", "data"):
            if isinstance(bruto.get(k), list):
                lista = bruto[k]
                break
    if not isinstance(lista, list):
        return pd.DataFrame(), resp, atualizacao

    df = pd.DataFrame(lista)
    if "Codigo" in df:
        # O codigo vem com pontos (0101.21.00); a versao so com digitos
        # facilita a busca por prefixo de capitulo e posicao.
        df["Codigo_limpo"] = df["Codigo"].astype(str).str.replace(r"\D", "", regex=True)
        df["Capitulo"] = df["Codigo_limpo"].str[:2]
    return df, resp, atualizacao


def filtrar_ncm(df: pd.DataFrame, termo: str) -> pd.DataFrame:
    if df.empty or not termo:
        return df
    alvo = termo.strip().upper()
    digitos = "".join(ch for ch in alvo if ch.isdigit())
    mascara = df["Descricao"].astype(str).str.upper().str.contains(alvo, na=False)
    if digitos:
        mascara = mascara | df["Codigo_limpo"].astype(str).str.startswith(digitos)
    return df[mascara]


# ---------------------------------------------------------------------------
# CNAE
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def cnae(nivel: str = "classes", forcar: bool = False):
    """nivel: secoes, divisoes, grupos ou classes."""
    resp = http.obter_json("%s/%s" % (CNAE_IBGE, nivel), TTL_CADASTRAL,
                           "IBGE/CNAE %s" % nivel, forcar, timeout=90)
    if not resp.ok or not isinstance(resp.dados, list):
        return pd.DataFrame(), resp
    return pd.json_normalize(resp.dados), resp


# ---------------------------------------------------------------------------
# CVM - companhias abertas
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def companhias_abertas(forcar: bool = False):
    """Cadastro oficial das companhias abertas registradas na CVM."""
    resp = http.obter_texto(CVM_CADASTRO, TTL_CADASTRAL, "CVM/Companhias abertas",
                            forcar, codificacao="latin-1")
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    try:
        df = pd.read_csv(io.StringIO(resp.dados), sep=";", dtype=str,
                         on_bad_lines="skip")
    except Exception as exc:
        resp.erro = "Falha ao interpretar o CSV da CVM: %s" % type(exc).__name__
        return pd.DataFrame(), resp
    return df, resp


# ---------------------------------------------------------------------------
# CVM - fundos de investimento
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def fundos_cadastro(forcar: bool = False):
    """Cadastro de todos os fundos de investimento (cad_fi.csv, ~18 MB)."""
    resp = http.obter_texto(CVM_FUNDOS_CAD, TTL_CADASTRAL, "CVM/Cadastro de fundos",
                            forcar, codificacao="latin-1")
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    try:
        df = pd.read_csv(io.StringIO(resp.dados), sep=";", dtype=str,
                         on_bad_lines="skip")
    except Exception as exc:
        resp.erro = "Falha ao interpretar o cadastro de fundos: %s" % type(exc).__name__
        return pd.DataFrame(), resp
    return df, resp


def filtrar_fundos(df: pd.DataFrame, termo: str, situacao: str = "") -> pd.DataFrame:
    if df.empty:
        return df
    filtrado = df
    if situacao and "SIT" in df:
        filtrado = filtrado[filtrado["SIT"] == situacao]
    if termo:
        alvo = termo.strip().upper()
        dig = "".join(c for c in alvo if c.isdigit())
        col_nome = "DENOM_SOCIAL" if "DENOM_SOCIAL" in filtrado else None
        # mascara sempre uma Series booleana (nunca escalar False, que quebraria
        # a indexacao df[mascara] com KeyError se a coluna de nome nao existir).
        mascara = (filtrado[col_nome].astype(str).str.upper().str.contains(alvo, na=False)
                   if col_nome else pd.Series(False, index=filtrado.index))
        if dig and "CNPJ_FUNDO" in filtrado:
            mascara = mascara | filtrado["CNPJ_FUNDO"].astype(str).str.replace(
                r"\D", "", regex=True).str.contains(dig, na=False)
        filtrado = filtrado[mascara]
    return filtrado


def _zip_informe_local(anomes: str, forcar: bool = False):
    """Baixa o zip do informe diario para o cache local (uma vez por mes).

    O informe mensal deszipa em um CSV grande (milhoes de linhas); guardar o
    zip localmente evita rebaixar 11 MB a cada consulta e evita inflar o cache
    JSON. Devolve o caminho do zip ou (None, erro).
    """
    destino = DIR_CACHE / ("inf_diario_fi_%s.zip" % anomes)
    if destino.exists() and not forcar:
        idade = time.time() - destino.stat().st_mtime
        if idade < TTL_MENSAL:
            return destino, ""
    try:
        resp = http.sessao().get(CVM_FUNDOS_INF % anomes, timeout=180, stream=True)
        if resp.status_code != 200:
            if destino.exists():
                return destino, ""      # usa a copia velha se houver
            return None, "HTTP %d ao baixar o informe de %s." % (resp.status_code, anomes)
        tmp = destino.with_suffix(".part")
        with tmp.open("wb") as fh:
            for bloco in resp.iter_content(65536):
                fh.write(bloco)
        tmp.replace(destino)
        return destino, ""
    except Exception as exc:
        if destino.exists():
            return destino, ""
        return None, "Falha ao baixar o informe: %s" % type(exc).__name__


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def informe_diario_fundo(cnpj: str, anomes: str, forcar: bool = False):
    """Serie diaria de cota e patrimonio de UM fundo no mes.

    Le o CSV do zip em blocos e mantem so as linhas do CNPJ pedido - assim a
    memoria fica limitada as poucas dezenas de linhas do fundo, e nao aos
    milhoes de linhas do informe inteiro.
    """
    dig = "".join(c for c in str(cnpj) if c.isdigit())
    if len(dig) != 14:
        return pd.DataFrame(), "Informe um CNPJ de fundo com 14 digitos."
    # anomes entra no nome do arquivo e na URL: exigir exatamente AAAAMM barra
    # qualquer tentativa de path traversal ou injecao na URL.
    if not (isinstance(anomes, str) and re.fullmatch(r"\d{6}", anomes)):
        return pd.DataFrame(), "Periodo invalido (use AAAAMM)."
    caminho_zip, erro = _zip_informe_local(anomes, forcar)
    if not caminho_zip:
        return pd.DataFrame(), erro

    cnpj_fmt = "%s.%s.%s/%s-%s" % (dig[:2], dig[2:5], dig[5:8], dig[8:12], dig[12:])
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            nome_csv = next((n for n in z.namelist() if n.lower().endswith(".csv")),
                            None)
            if not nome_csv:
                return pd.DataFrame(), "O zip do informe nao contem CSV."
            partes = []
            with z.open(nome_csv) as fh:
                for bloco in pd.read_csv(fh, sep=";", dtype=str, encoding="latin-1",
                                         chunksize=200000, on_bad_lines="skip"):
                    # Desde a Resolucao CVM 175 (regime FIF), o informe identifica
                    # a CLASSE do fundo em CNPJ_FUNDO_CLASSE; meses antigos usavam
                    # CNPJ_FUNDO. Aceita as duas colunas, formato com ou sem pontos.
                    col = next((c for c in ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")
                                if c in bloco.columns), None)
                    if not col:
                        continue
                    serie = bloco[col].astype(str)
                    recorte = bloco[serie.isin([cnpj_fmt, dig])
                                    | (serie.str.replace(r"\D", "", regex=True) == dig)]
                    if not recorte.empty:
                        partes.append(recorte)
    except Exception as exc:
        return pd.DataFrame(), "Falha ao ler o informe: %s" % type(exc).__name__

    if not partes:
        return pd.DataFrame(), ""
    df = pd.concat(partes, ignore_index=True)
    for col in ("VL_QUOTA", "VL_PATRIM_LIQ", "CAPTC_DIA", "RESG_DIA", "VL_TOTAL"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "DT_COMPTC" in df:
        df["DT_COMPTC"] = pd.to_datetime(df["DT_COMPTC"], errors="coerce")
        df = df.sort_values("DT_COMPTC")
    return df, ""
