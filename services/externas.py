# -*- coding: utf-8 -*-
"""Demais APIs publicas brasileiras, todas sem chave de acesso.

  IBGE          -> servicodados.ibge.gov.br  (localidades e agregados/SIDRA)
  BrasilAPI     -> brasilapi.com.br          (CNPJ, CEP, bancos, Pix, feriados)
  Open Finance  -> data.directory.openbankingbrasil.org.br (diretorio publico)

O diretorio do Open Finance e o unico ponto realmente aberto do ecossistema:
lista todas as instituicoes participantes, suas marcas e os endpoints das APIs
de dados abertos (produtos, servicos e canais) que cada uma publica sem exigir
certificado. Dados de cliente exigem ser instituicao regulada e ficam fora.
"""
import pandas as pd
import streamlit as st

from core import http
from core.config import TTL_CADASTRAL, TTL_DIARIO, TTL_MEMORIA

IBGE = "https://servicodados.ibge.gov.br/api"
BRASILAPI = "https://brasilapi.com.br/api"
OF_DIRETORIO = "https://data.directory.openbankingbrasil.org.br/participants"


# ---------------------------------------------------------------------------
# IBGE
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ibge_estados(forcar: bool = False):
    resp = http.obter_json("%s/v1/localidades/estados?orderBy=nome" % IBGE,
                           TTL_CADASTRAL, "IBGE/Estados", forcar)
    if not resp.ok:
        return pd.DataFrame(), resp
    df = pd.json_normalize(resp.dados)
    return df, resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ibge_municipios(uf: str, forcar: bool = False):
    resp = http.obter_json("%s/v1/localidades/estados/%s/municipios" % (IBGE, uf),
                           TTL_CADASTRAL, "IBGE/Municipios %s" % uf, forcar)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.json_normalize(resp.dados), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ibge_agregado(agregado: int, variavel: int, periodos: str = "-12",
                  nivel: str = "N1[all]", forcar: bool = False):
    """Serie de um agregado do SIDRA. Ex.: 1737/63 = IPCA variacao mensal."""
    url = "%s/v3/agregados/%d/periodos/%s/variaveis/%d?localidades=%s" % (
        IBGE, int(agregado), periodos, int(variavel), nivel
    )
    resp = http.obter_json(url, TTL_DIARIO,
                           "IBGE/Agregado %s var %s" % (agregado, variavel), forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    linhas = []
    for bloco in resp.dados:
        unidade = bloco.get("unidade", "")
        for serie in bloco.get("resultados", []):
            for item in serie.get("series", []):
                local = item.get("localidade", {}).get("nome", "")
                for periodo, valor in (item.get("serie") or {}).items():
                    linhas.append({
                        "Periodo": periodo,
                        "Localidade": local,
                        "Valor": pd.to_numeric(valor, errors="coerce"),
                        "Unidade": unidade,
                    })
    return pd.DataFrame(linhas), resp


AGREGADOS_IBGE = {
    "IPCA - variacao mensal": {"agregado": 1737, "variavel": 63},
    "IPCA - acumulado no ano": {"agregado": 1737, "variavel": 69},
    "IPCA - acumulado 12 meses": {"agregado": 1737, "variavel": 2265},
    "INPC - variacao mensal": {"agregado": 1736, "variavel": 44},
}


# ---------------------------------------------------------------------------
# BrasilAPI
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def bancos(forcar: bool = False):
    resp = http.obter_json("%s/banks/v1" % BRASILAPI, TTL_CADASTRAL,
                           "BrasilAPI/Bancos", forcar)
    if not resp.ok:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    colunas = [c for c in ("code", "name", "fullName", "ispb") if c in df]
    return df[colunas] if colunas else df, resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def participantes_pix(forcar: bool = False):
    resp = http.obter_json("%s/pix/v1/participants" % BRASILAPI, TTL_CADASTRAL,
                           "BrasilAPI/Participantes Pix", forcar)
    return (pd.DataFrame(resp.dados) if resp.ok else pd.DataFrame()), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def feriados(ano: int, forcar: bool = False):
    resp = http.obter_json("%s/feriados/v1/%d" % (BRASILAPI, int(ano)), TTL_CADASTRAL,
                           "BrasilAPI/Feriados %d" % ano, forcar)
    return (pd.DataFrame(resp.dados) if resp.ok else pd.DataFrame()), resp


def consultar_cnpj(cnpj: str):
    """Consulta pontual de CNPJ. Sem cache em disco: dado de terceiro."""
    limpo = "".join(ch for ch in str(cnpj) if ch.isdigit())
    if len(limpo) != 14:
        return None, "Informe um CNPJ com 14 digitos."
    try:
        resp = http.sessao().get("%s/cnpj/v1/%s" % (BRASILAPI, limpo), timeout=25)
        if resp.status_code == 404:
            return None, "CNPJ nao encontrado na base publica."
        resp.raise_for_status()
        return resp.json(), ""
    except Exception as exc:
        return None, "Falha na consulta: %s" % type(exc).__name__


def consultar_cep(cep: str):
    limpo = "".join(ch for ch in str(cep) if ch.isdigit())
    if len(limpo) != 8:
        return None, "Informe um CEP com 8 digitos."
    try:
        resp = http.sessao().get("%s/cep/v2/%s" % (BRASILAPI, limpo), timeout=20)
        if resp.status_code == 404:
            return None, "CEP nao encontrado."
        resp.raise_for_status()
        return resp.json(), ""
    except Exception as exc:
        return None, "Falha na consulta: %s" % type(exc).__name__


# ---------------------------------------------------------------------------
# Open Finance Brasil - diretorio publico de participantes
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def openfinance_participantes(forcar: bool = False):
    """Instituicoes participantes, uma linha por marca."""
    resp = http.obter_json(OF_DIRETORIO, TTL_CADASTRAL,
                           "OpenFinance/Diretorio", forcar)
    if not resp.ok or not isinstance(resp.dados, list):
        return pd.DataFrame(), resp
    linhas = []
    for org in resp.dados:
        servidores = org.get("AuthorisationServers") or []
        familias = set()
        for s in servidores:
            for r in (s.get("ApiResources") or []):
                if r.get("ApiFamilyType"):
                    familias.add(r["ApiFamilyType"])
        linhas.append({
            "Instituicao": org.get("OrganisationName"),
            "CNPJ": org.get("RegistrationNumber"),
            "Situacao": org.get("Status"),
            "Marcas": ", ".join(
                sorted({s.get("CustomerFriendlyName", "") for s in servidores if s.get("CustomerFriendlyName")})
            ),
            "Qtd. marcas": len(servidores),
            "Familias de API": ", ".join(sorted(familias)),
            "Qtd. familias": len(familias),
            "Cidade": org.get("City"),
        })
    df = pd.DataFrame(linhas)
    if not df.empty:
        df = df.sort_values("Instituicao")
    return df, resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def openfinance_endpoints(forcar: bool = False):
    """Endpoints publicados por marca e familia de API."""
    resp = http.obter_json(OF_DIRETORIO, TTL_CADASTRAL,
                           "OpenFinance/Diretorio", forcar)
    if not resp.ok or not isinstance(resp.dados, list):
        return pd.DataFrame(), resp
    linhas = []
    for org in resp.dados:
        for s in (org.get("AuthorisationServers") or []):
            for r in (s.get("ApiResources") or []):
                for ep in (r.get("ApiDiscoveryEndpoints") or []):
                    linhas.append({
                        "Instituicao": org.get("OrganisationName"),
                        "Marca": s.get("CustomerFriendlyName"),
                        "Familia": r.get("ApiFamilyType"),
                        "Versao": r.get("ApiVersion"),
                        "Certificacao": r.get("CertificationStatus"),
                        "Endpoint": ep.get("ApiEndpoint"),
                    })
    return pd.DataFrame(linhas), resp


# Familias de API do Open Finance que sao de acesso publico (fase de dados
# abertos): nao exigem consentimento, certificado nem OAuth.
FAMILIAS_ABERTAS = {
    "products-services": "Produtos e servicos: taxas, tarifas e condicoes por produto",
    "channels": "Canais de atendimento: agencias, caixas eletronicos, telefones",
    "discovery": "Descoberta: catalogo de endpoints da propria instituicao",
}
