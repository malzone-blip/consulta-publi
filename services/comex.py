# -*- coding: utf-8 -*-
"""Comercio exterior: ComexStat (MDIC) e paises (IBGE).

O ComexStat so aceita consulta por POST, com o recorte descrito no corpo da
requisicao. Por isso usa http.enviar_json, que aplica o mesmo cache em disco
das demais fontes, com a chave derivada de URL + corpo.
"""
import pandas as pd
import streamlit as st

from core import http
from core.config import TTL_CADASTRAL, TTL_DIARIO, TTL_MEMORIA

COMEXSTAT = "https://api-comexstat.mdic.gov.br"
PAISES_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/paises"

FLUXOS = {"export": "Exportacao", "import": "Importacao"}

RECORTES = {
    "country": "Pais de destino/origem",
    "state": "Unidade da federacao",
    "ncm": "NCM (produto)",
    "economicBlock": "Bloco economico",
    "section": "Secao do sistema harmonizado",
    "via": "Via de transporte",
    "urf": "Unidade da Receita Federal",
}

METRICAS = {
    "metricFOB": "Valor FOB (US$)",
    "metricKG": "Peso liquido (kg)",
    "metricStatistic": "Quantidade estatistica",
}


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ultima_atualizacao(forcar: bool = False):
    resp = http.obter_json("%s/general/dates/updated" % COMEXSTAT, TTL_DIARIO,
                           "ComexStat/Atualizacao", forcar)
    if not resp.ok:
        return "", resp
    dados = resp.dados.get("data") if isinstance(resp.dados, dict) else None
    if isinstance(dados, dict):
        return str(dados.get("updated") or dados.get("date") or ""), resp
    return str(dados or ""), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def balanca(fluxo: str, de: str, ate: str, recortes: tuple,
            metricas: tuple = ("metricFOB", "metricKG"),
            detalhe_mensal: bool = False, forcar: bool = False):
    """Consulta agregada de exportacao ou importacao.

    de / ate no formato AAAA-MM. 'recortes' define as dimensoes de quebra.
    """
    corpo = {
        "flow": fluxo,
        "monthDetail": bool(detalhe_mensal),
        "period": {"from": de, "to": ate},
        "filters": [],
        "details": list(recortes),
        "metrics": list(metricas),
    }
    resp = http.enviar_json("%s/general" % COMEXSTAT, corpo, TTL_DIARIO,
                            "ComexStat %s %s..%s" % (fluxo, de, ate), forcar,
                            timeout=120)
    if not resp.ok:
        return pd.DataFrame(), resp

    pacote = resp.dados if isinstance(resp.dados, dict) else {}
    if pacote.get("success") is False:
        resp.erro = str(pacote.get("message") or "O ComexStat recusou a consulta.")
        return pd.DataFrame(), resp

    conteudo = pacote.get("data") or {}
    lista = conteudo.get("list") if isinstance(conteudo, dict) else None
    if not lista:
        return pd.DataFrame(), resp

    df = pd.DataFrame(lista)
    for coluna in ("metricFOB", "metricKG", "metricStatistic"):
        if coluna in df:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df, resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def paises(forcar: bool = False):
    resp = http.obter_json(PAISES_IBGE, TTL_CADASTRAL, "IBGE/Paises", forcar,
                           timeout=90)
    if not resp.ok or not isinstance(resp.dados, list):
        return pd.DataFrame(), resp
    df = pd.json_normalize(resp.dados)
    colunas = {c: c.split(".")[-1] for c in df.columns}
    return df.rename(columns=colunas), resp
