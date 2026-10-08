# -*- coding: utf-8 -*-
"""Fontes juridicas publicas.

  DataJud (CNJ)     -> metadados processuais de todos os tribunais do pais
  Camara / Senado   -> tramitacao legislativa federal
  Querido Diario    -> diarios oficiais municipais com busca em texto

Sobre a chave do DataJud: o CNJ publica uma chave unica e igual para todos na
documentacao da API Publica. Nao e credencial de ninguem - e o equivalente a
uma senha de porta aberta, exigida so para o orgao medir o uso.
"""
import pandas as pd
import streamlit as st

from core import db, http
from core.config import (CFG_CHAVE_DATAJUD, CHAVE_DATAJUD_PADRAO, TTL_CADASTRAL,
                         TTL_DIARIO, TTL_MEMORIA, TIMEOUT_LENTO)

DATAJUD = "https://api-publica.datajud.cnj.jus.br"
CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
QUERIDO_DIARIO = "https://queridodiario.ok.org.br/api"


# ---------------------------------------------------------------------------
# DataJud - CNJ
# ---------------------------------------------------------------------------
def _tribunais():
    """Aliases da API Publica, no formato api_publica_<sigla>."""
    superiores = {"stj": "STJ - Superior Tribunal de Justica",
                  "tst": "TST - Tribunal Superior do Trabalho",
                  "tse": "TSE - Tribunal Superior Eleitoral",
                  "stm": "STM - Superior Tribunal Militar"}
    federais = {"trf%d" % i: "TRF%d - Tribunal Regional Federal da %da Regiao" % (i, i)
                for i in range(1, 7)}
    ufs = ["ac", "al", "am", "ap", "ba", "ce", "df", "es", "go", "ma", "mg", "ms",
           "mt", "pa", "pb", "pe", "pi", "pr", "rj", "rn", "ro", "rr", "rs", "sc",
           "se", "sp", "to"]
    estaduais = {"tj%s" % uf: "TJ%s - Tribunal de Justica de %s"
                 % (uf.upper(), uf.upper()) for uf in ufs}
    trabalho = {"trt%d" % i: "TRT%d - Tribunal Regional do Trabalho da %da Regiao"
                % (i, i) for i in range(1, 25)}
    saida = {}
    for grupo in (superiores, federais, estaduais, trabalho):
        for sigla, nome in grupo.items():
            saida["api_publica_%s" % sigla] = nome
    return saida


TRIBUNAIS = _tribunais()


def _data_br(iso) -> str:
    """AAAA-MM-DD(THH:MM...) -> dd/mm/aaaa. Devolve '' se nao reconhecer."""
    s = str(iso or "")[:10]
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return "%s/%s/%s" % (s[8:10], s[5:7], s[0:4])
    return s


def chave_datajud() -> str:
    return db.obter_config(CFG_CHAVE_DATAJUD, CHAVE_DATAJUD_PADRAO)


def _cabecalhos_datajud() -> dict:
    return {"Authorization": "APIKey %s" % chave_datajud(),
            "Content-Type": "application/json"}


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def processos(alias: str, numero: str = "", classe: str = "", orgao: str = "",
              desde: str = "", ate: str = "", tamanho: int = 50,
              forcar: bool = False):
    """Consulta processual no DataJud.

    numero: aceita o CNJ formatado ou so os digitos.
    desde / ate: AAAA-MM-DD, aplicados sobre a data de ajuizamento.
    """
    condicoes = []
    digitos = "".join(ch for ch in (numero or "") if ch.isdigit())
    if digitos:
        condicoes.append({"match": {"numeroProcesso": digitos}})
    if classe:
        condicoes.append({"match": {"classe.nome": classe}})
    if orgao:
        condicoes.append({"match": {"orgaoJulgador.nome": orgao}})
    if desde or ate:
        faixa = {}
        if desde:
            faixa["gte"] = desde
        if ate:
            faixa["lte"] = ate
        condicoes.append({"range": {"dataAjuizamento": faixa}})

    consulta = {"bool": {"must": condicoes}} if condicoes else {"match_all": {}}
    corpo = {"size": int(tamanho), "query": consulta,
             "sort": [{"dataAjuizamento": {"order": "desc"}}]}

    resp = http.enviar_json("%s/%s/_search" % (DATAJUD, alias), corpo, TTL_DIARIO,
                            "DataJud/%s" % alias, forcar,
                            cabecalhos=_cabecalhos_datajud(), timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp, 0

    hits = ((resp.dados or {}).get("hits") or {})
    total = (hits.get("total") or {}).get("value", 0)
    registros = []
    for h in hits.get("hits", []):
        f = h.get("_source", {}) or {}
        movimentos = f.get("movimentos") or []
        assuntos = f.get("assuntos") or []
        # datas do DataJud vem em ISO (AAAA-MM-DD); exibir em dd/mm/aaaa
        # Guardar pela lista JA filtrada por dataHora: alguns tribunais mandam
        # movimentos sem dataHora, e guardar por 'movimentos' faria sorted([])[-1]
        # estourar IndexError e derrubar a montagem inteira.
        datados = sorted([m for m in movimentos if m.get("dataHora")],
                         key=lambda m: m["dataHora"])
        registros.append({
            "Processo": f.get("numeroProcesso"),
            "Tribunal": f.get("tribunal"),
            "Grau": f.get("grau"),
            "Ajuizamento": _data_br(f.get("dataAjuizamento")),
            "Classe": (f.get("classe") or {}).get("nome"),
            "Orgao julgador": (f.get("orgaoJulgador") or {}).get("nome"),
            "Assuntos": ", ".join(a.get("nome", "") for a in assuntos if a.get("nome")),
            "Movimentos": len(movimentos),
            "Ultimo movimento": datados[-1].get("nome") if datados else "",
            "Sistema": (f.get("sistema") or {}).get("nome"),
            "Formato": (f.get("formato") or {}).get("nome"),
            "Atualizado": _data_br(f.get("dataHoraUltimaAtualizacao")),
        })
    return pd.DataFrame(registros), resp, total


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def movimentos_do_processo(alias: str, numero: str, forcar: bool = False):
    """Linha do tempo completa de um processo."""
    digitos = "".join(ch for ch in (numero or "") if ch.isdigit())
    if not digitos:
        return pd.DataFrame(), None
    corpo = {"size": 1, "query": {"match": {"numeroProcesso": digitos}}}
    resp = http.enviar_json("%s/%s/_search" % (DATAJUD, alias), corpo, TTL_DIARIO,
                            "DataJud/%s mov %s" % (alias, digitos), forcar,
                            cabecalhos=_cabecalhos_datajud(), timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    hits = ((resp.dados or {}).get("hits") or {}).get("hits", [])
    if not hits:
        return pd.DataFrame(), resp
    movimentos = hits[0].get("_source", {}).get("movimentos") or []
    # ordena pelo ISO (ordenavel) antes de formatar a data para dd/mm/aaaa
    movimentos = sorted(movimentos, key=lambda m: m.get("dataHora") or "", reverse=True)
    linhas = [{
        "Data": _data_br(m.get("dataHora")),
        "Hora": (m.get("dataHora") or "")[11:19],
        "Movimento": m.get("nome"),
        "Codigo": m.get("codigo"),
        "Complementos": ", ".join(
            c.get("descricao", "") for c in (m.get("complementosTabelados") or [])),
    } for m in movimentos]
    return pd.DataFrame(linhas), resp


# ---------------------------------------------------------------------------
# Camara dos Deputados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def proposicoes_camara(ano: int, sigla: str = "", termo: str = "",
                       itens: int = 100, forcar: bool = False):
    partes = ["ano=%d" % int(ano), "itens=%d" % int(itens),
              "ordem=DESC", "ordenarPor=id"]
    if sigla:
        partes.append("siglaTipo=%s" % sigla)
    if termo:
        from urllib.parse import quote
        partes.append("keywords=%s" % quote(termo))
    url = "%s/proposicoes?%s" % (CAMARA, "&".join(partes))
    resp = http.obter_json(url, TTL_DIARIO, "Camara/Proposicoes %s" % ano, forcar,
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    dados = (resp.dados or {}).get("dados") or []
    return pd.DataFrame(dados), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def deputados(uf: str = "", partido: str = "", forcar: bool = False):
    partes = ["itens=513", "ordem=ASC", "ordenarPor=nome"]
    if uf:
        partes.append("siglaUf=%s" % uf)
    if partido:
        partes.append("siglaPartido=%s" % partido)
    url = "%s/deputados?%s" % (CAMARA, "&".join(partes))
    resp = http.obter_json(url, TTL_CADASTRAL, "Camara/Deputados", forcar,
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.DataFrame((resp.dados or {}).get("dados") or []), resp


# ---------------------------------------------------------------------------
# Senado Federal
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def materias_senado(ano: int, sigla: str = "PL", forcar: bool = False):
    url = "%s/materia/pesquisa/lista?ano=%d&sigla=%s" % (SENADO, int(ano), sigla)
    resp = http.obter_json(url, TTL_DIARIO, "Senado/Materias %s %s" % (sigla, ano),
                           forcar, cabecalhos={"Accept": "application/json"},
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    raiz = (resp.dados or {}).get("PesquisaBasicaMateria") or {}
    materias = (((raiz.get("Materias") or {}).get("Materia")) or [])
    if isinstance(materias, dict):
        materias = [materias]
    linhas = []
    for m in materias:
        ident = m.get("IdentificacaoMateria") or {}
        dados = m.get("DadosBasicosMateria") or {}
        linhas.append({
            "Codigo": ident.get("CodigoMateria"),
            "Sigla": ident.get("SiglaSubtipoMateria"),
            "Numero": ident.get("NumeroMateria"),
            "Ano": ident.get("AnoMateria"),
            "Apresentacao": dados.get("DataApresentacao"),
            "Ementa": dados.get("EmentaMateria"),
            "Autor": (m.get("Autoria") or {}).get("Autor", {}).get("NomeAutor")
                     if isinstance((m.get("Autoria") or {}).get("Autor"), dict) else "",
        })
    return pd.DataFrame(linhas), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def senadores(forcar: bool = False):
    resp = http.obter_json("%s/senador/lista/atual" % SENADO, TTL_CADASTRAL,
                           "Senado/Senadores", forcar,
                           cabecalhos={"Accept": "application/json"})
    if not resp.ok:
        return pd.DataFrame(), resp
    raiz = (resp.dados or {}).get("ListaParlamentarEmExercicio") or {}
    lista = (((raiz.get("Parlamentares") or {}).get("Parlamentar")) or [])
    if isinstance(lista, dict):
        lista = [lista]
    linhas = []
    for p in lista:
        ident = p.get("IdentificacaoParlamentar") or {}
        linhas.append({
            "Nome": ident.get("NomeParlamentar"),
            "Nome completo": ident.get("NomeCompletoParlamentar"),
            "Partido": ident.get("SiglaPartidoParlamentar"),
            "UF": ident.get("UfParlamentar"),
            "E-mail": ident.get("EmailParlamentar"),
        })
    return pd.DataFrame(linhas), resp


# ---------------------------------------------------------------------------
# Querido Diario - diarios oficiais municipais
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def cidades_diario(nome: str, forcar: bool = False):
    from urllib.parse import quote
    resp = http.obter_json("%s/cities?city_name=%s" % (QUERIDO_DIARIO, quote(nome)),
                           TTL_CADASTRAL, "QueridoDiario/Cidades %s" % nome, forcar,
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp
    return pd.DataFrame((resp.dados or {}).get("cities") or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def diarios(territorios: tuple, termo: str = "", desde: str = "", ate: str = "",
            tamanho: int = 30, forcar: bool = False):
    from urllib.parse import quote
    partes = ["size=%d" % int(tamanho), "sort_by=descending_date"]
    for t in territorios:
        partes.append("territory_ids=%s" % t)
    if termo:
        partes.append("querystring=%s" % quote(termo))
    if desde:
        partes.append("published_since=%s" % desde)
    if ate:
        partes.append("published_until=%s" % ate)
    url = "%s/gazettes?%s" % (QUERIDO_DIARIO, "&".join(partes))
    resp = http.obter_json(url, TTL_DIARIO, "QueridoDiario/Gazetas", forcar,
                           timeout=TIMEOUT_LENTO)
    if not resp.ok:
        return pd.DataFrame(), resp, 0
    pacote = resp.dados or {}
    linhas = []
    for g in pacote.get("gazettes") or []:
        trechos = g.get("excerpts") or []
        linhas.append({
            "Data": g.get("date"),
            "Municipio": g.get("territory_name"),
            "UF": g.get("state_code"),
            "Edicao": g.get("edition"),
            "Extra": "Sim" if g.get("is_extra_edition") else "Nao",
            "Trecho": (trechos[0][:300] + "...") if trechos else "",
            "Link": g.get("url"),
        })
    return pd.DataFrame(linhas), resp, pacote.get("total_gazettes", len(linhas))
