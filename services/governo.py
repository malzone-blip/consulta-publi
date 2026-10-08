# -*- coding: utf-8 -*-
"""Contas publicas e contratacoes governamentais.

  SICONFI (Tesouro Nacional) -> RREO, RGF e DCA de estados e municipios
  PNCP                       -> contratos, atas e contratacoes da Lei 14.133
  Compras.gov.br             -> catalogo de materiais e servicos

Nenhuma exige chave.
"""
import pandas as pd
import streamlit as st

from core import http
from core.config import TTL_CADASTRAL, TTL_DIARIO, TTL_MEMORIA, TIMEOUT_LENTO

SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
PNCP = "https://pncp.gov.br/api/consulta/v1"
COMPRAS = "https://dadosabertos.compras.gov.br"


# ---------------------------------------------------------------------------
# SICONFI - Tesouro Nacional
# ---------------------------------------------------------------------------
ESFERAS = {"U": "Uniao", "E": "Estado / DF", "M": "Municipio"}

ANEXOS_RREO = [
    "RREO-Anexo 01", "RREO-Anexo 02", "RREO-Anexo 03", "RREO-Anexo 04",
    "RREO-Anexo 06", "RREO-Anexo 07", "RREO-Anexo 10", "RREO-Anexo 12",
    "RREO-Anexo 13", "RREO-Anexo 14",
]
ANEXOS_RGF = ["RGF-Anexo 01", "RGF-Anexo 02", "RGF-Anexo 03", "RGF-Anexo 04",
              "RGF-Anexo 05", "RGF-Anexo 06"]


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def entes(forcar: bool = False):
    """Todos os entes federativos com codigo IBGE, UF, esfera e populacao."""
    resp = http.obter_json("%s/entes" % SICONFI, TTL_CADASTRAL, "SICONFI/Entes",
                           forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    itens = (resp.dados or {}).get("items") or []
    return pd.DataFrame(itens), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def rreo(exercicio: int, periodo: int, anexo: str, esfera: str, id_ente: str,
         forcar: bool = False):
    """Relatorio Resumido da Execucao Orcamentaria (bimestral)."""
    from urllib.parse import quote
    url = ("%s/rreo?an_exercicio=%d&nr_periodo=%d&co_tipo_demonstrativo=RREO"
           "&no_anexo=%s&co_esfera=%s&id_ente=%s"
           % (SICONFI, int(exercicio), int(periodo), quote(anexo), esfera, id_ente))
    resp = http.obter_json(url, TTL_CADASTRAL,
                           "SICONFI/RREO %s %s/%s" % (id_ente, periodo, exercicio),
                           forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.DataFrame((resp.dados or {}).get("items") or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def rgf(exercicio: int, periodo: int, anexo: str, esfera: str, id_ente: str,
        poder: str = "E", forcar: bool = False):
    """Relatorio de Gestao Fiscal (quadrimestral). poder: E, L, J, M ou D."""
    from urllib.parse import quote
    url = ("%s/rgf?an_exercicio=%d&in_periodicidade=Q&nr_periodo=%d"
           "&co_tipo_demonstrativo=RGF&no_anexo=%s&co_esfera=%s&co_poder=%s&id_ente=%s"
           % (SICONFI, int(exercicio), int(periodo), quote(anexo), esfera, poder, id_ente))
    resp = http.obter_json(url, TTL_CADASTRAL,
                           "SICONFI/RGF %s %s/%s" % (id_ente, periodo, exercicio),
                           forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.DataFrame((resp.dados or {}).get("items") or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def dca(exercicio: int, anexo: str, id_ente: str, forcar: bool = False):
    """Declaracao de Contas Anuais."""
    from urllib.parse import quote
    url = ("%s/dca?an_exercicio=%d&no_anexo=%s&id_ente=%s"
           % (SICONFI, int(exercicio), quote(anexo), id_ente))
    resp = http.obter_json(url, TTL_CADASTRAL, "SICONFI/DCA %s %s" % (id_ente, exercicio),
                           forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.DataFrame((resp.dados or {}).get("items") or []), resp


# ---------------------------------------------------------------------------
# PNCP - Portal Nacional de Contratacoes Publicas
# ---------------------------------------------------------------------------
MODALIDADES = {
    1: "Leilao eletronico", 2: "Dialogo competitivo", 3: "Concurso",
    4: "Concorrencia eletronica", 5: "Concorrencia presencial",
    6: "Pregao eletronico", 7: "Pregao presencial", 8: "Dispensa de licitacao",
    9: "Inexigibilidade", 10: "Manifestacao de interesse",
    11: "Pre-qualificacao", 12: "Credenciamento", 13: "Leilao presencial",
}


def _data_pncp(d) -> str:
    return d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d).replace("-", "")


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pncp_contratos(de, ate, cnpj_orgao: str = "", pagina: int = 1,
                   forcar: bool = False):
    url = "%s/contratos?dataInicial=%s&dataFinal=%s&pagina=%d" % (
        PNCP, _data_pncp(de), _data_pncp(ate), int(pagina))
    if cnpj_orgao:
        url += "&cnpjOrgao=%s" % "".join(c for c in cnpj_orgao if c.isdigit())
    resp = http.obter_json(url, TTL_DIARIO, "PNCP/Contratos", forcar,
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp, 0
    pacote = resp.dados or {}
    dados = pacote.get("data") or []
    return pd.json_normalize(dados), resp, pacote.get("totalRegistros", len(dados))


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pncp_atas(de, ate, pagina: int = 1, forcar: bool = False):
    url = "%s/atas?dataInicial=%s&dataFinal=%s&pagina=%d" % (
        PNCP, _data_pncp(de), _data_pncp(ate), int(pagina))
    resp = http.obter_json(url, TTL_DIARIO, "PNCP/Atas", forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp, 0
    pacote = resp.dados or {}
    dados = pacote.get("data") or []
    return pd.json_normalize(dados), resp, pacote.get("totalRegistros", len(dados))


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pncp_contratacoes(de, ate, modalidade: int = 8, pagina: int = 1,
                      forcar: bool = False):
    url = ("%s/contratacoes/publicacao?dataInicial=%s&dataFinal=%s"
           "&codigoModalidadeContratacao=%d&pagina=%d"
           % (PNCP, _data_pncp(de), _data_pncp(ate), int(modalidade), int(pagina)))
    resp = http.obter_json(url, TTL_DIARIO, "PNCP/Contratacoes mod %d" % modalidade,
                           forcar, timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp, 0
    pacote = resp.dados or {}
    dados = pacote.get("data") or []
    return pd.json_normalize(dados), resp, pacote.get("totalRegistros", len(dados))


# ---------------------------------------------------------------------------
# Compras.gov.br - catalogo
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def catalogo_material(nivel: str = "grupo", pagina: int = 1, forcar: bool = False):
    """nivel: grupo ou classe. A API exige tamanhoPagina entre 10 e 500."""
    caminho = ("modulo-material/1_consultarGrupoMaterial" if nivel == "grupo"
               else "modulo-material/2_consultarClasseMaterial")
    url = "%s/%s?pagina=%d&tamanhoPagina=500" % (COMPRAS, caminho, int(pagina))
    resp = http.obter_json(url, TTL_CADASTRAL, "Compras.gov/%s de material" % nivel,
                           forcar, cabecalhos={"Accept": "application/json"},
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    pacote = resp.dados or {}
    dados = pacote.get("resultado") if isinstance(pacote, dict) else pacote
    return pd.DataFrame(dados or []), resp
