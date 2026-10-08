# -*- coding: utf-8 -*-
"""APIs publicas do Banco Central do Brasil.

Todos os endpoints abaixo foram verificados contra o servidor de producao.
Nenhum exige chave de acesso. Dois formatos convivem:

  SGS    -> api.bcb.gov.br/dados/serie/bcdata.sgs.<codigo>/dados
  Olinda -> olinda.bcb.gov.br/olinda/servico/<servico>/versao/v1/odata/<recurso>

No Olinda ha duas naturezas de recurso:
  - conjuntos de entidades, consultados direto  (ex.: Agencias)
  - funcoes parametrizadas, que exigem argumentos entre parenteses
    (ex.: ChavesPix(Data='2026-07-31'))
Chamar uma funcao sem os argumentos devolve HTTP 400 "URI is malformed".
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from core import http
from core.config import (TTL_CADASTRAL, TTL_DIARIO, TTL_INTRADIARIO, TTL_MEMORIA,
                         TTL_MENSAL)

# ---------------------------------------------------------------------------
# SGS - Sistema Gerenciador de Series Temporais
# ---------------------------------------------------------------------------
SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.%d/dados"

SERIES_SGS = {
    "Selic - meta definida pelo Copom (% a.a.)": {"codigo": 432, "unidade": "% a.a."},
    "Selic - taxa diaria (% a.d.)": {"codigo": 11, "unidade": "% a.d."},
    "Selic - acumulada no mes (%)": {"codigo": 4390, "unidade": "%"},
    "CDI - taxa diaria (% a.d.)": {"codigo": 12, "unidade": "% a.d."},
    "IPCA - variacao mensal (%)": {"codigo": 433, "unidade": "%"},
    "IPCA - acumulado 12 meses (%)": {"codigo": 13522, "unidade": "%"},
    "IGP-M - variacao mensal (%)": {"codigo": 189, "unidade": "%"},
    "INPC - variacao mensal (%)": {"codigo": 188, "unidade": "%"},
    "TR - taxa referencial (%)": {"codigo": 226, "unidade": "%"},
    "Dolar americano - venda (R$)": {"codigo": 1, "unidade": "R$"},
    "Euro - venda (R$)": {"codigo": 21619, "unidade": "R$"},
    "Poupanca - rendimento (%)": {"codigo": 195, "unidade": "%"},
    "Reservas internacionais (US$ milhoes)": {"codigo": 3546, "unidade": "US$ mi"},
    "Divida liquida do setor publico (% PIB)": {"codigo": 4513, "unidade": "% PIB"},
    "Saldo de credito total (R$ milhoes)": {"codigo": 20539, "unidade": "R$ mi"},
    "Inadimplencia da carteira de credito (%)": {"codigo": 21082, "unidade": "%"},
    "Endividamento das familias (%)": {"codigo": 29037, "unidade": "%"},
    "IBC-Br - indice de atividade economica": {"codigo": 24363, "unidade": "indice"},
}


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def serie_sgs(codigo: int, dias: int = 730, forcar: bool = False):
    """Historico de uma serie do SGS. Devolve (DataFrame, procedencia)."""
    fim = date.today()
    inicio = fim - timedelta(days=int(dias))
    url = "%s?formato=json&dataInicial=%s&dataFinal=%s" % (
        SGS % int(codigo), inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y")
    )
    resp = http.obter_json(url, TTL_DIARIO, "BCB/SGS serie %d" % codigo, forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(columns=["data", "valor"]), resp
    df = pd.DataFrame(resp.dados)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df.dropna(subset=["data"]).sort_values("data"), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ultimo_valor_sgs(codigo: int, dias: int = 120, forcar: bool = False):
    """Ultimo ponto disponivel de uma serie: (valor, data, procedencia)."""
    df, resp = serie_sgs(codigo, dias, forcar)
    if df.empty:
        return None, None, resp
    linha = df.iloc[-1]
    return float(linha["valor"]), linha["data"].date(), resp


# ---------------------------------------------------------------------------
# PTAX - cambio
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def moedas_ptax(forcar: bool = False):
    resp = http.olinda("PTAX", "Moedas", TTL_CADASTRAL, "BCB/PTAX moedas",
                       opcoes={"$orderby": "nomeFormatado"}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def cotacao_periodo(moeda: str, dias: int = 90, forcar: bool = False):
    """Cotacoes de uma moeda no periodo. A PTAX exige datas em MM-DD-AAAA."""
    fim = date.today()
    inicio = fim - timedelta(days=int(dias))
    resp = http.olinda(
        "PTAX", "CotacaoMoedaPeriodo", TTL_INTRADIARIO,
        "BCB/PTAX %s" % moeda,
        parametros={
            "moeda": "'%s'" % moeda,
            "dataInicial": "'%s'" % inicio.strftime("%m-%d-%Y"),
            "dataFinalCotacao": "'%s'" % fim.strftime("%m-%d-%Y"),
        },
        opcoes={"$orderby": "dataHoraCotacao desc", "$top": 5000},
        forcar=forcar,
    )
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    df["dataHoraCotacao"] = pd.to_datetime(df["dataHoraCotacao"], errors="coerce")
    for col in ("cotacaoCompra", "cotacaoVenda", "paridadeCompra", "paridadeVenda"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("dataHoraCotacao"), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def fechamento_recente(moeda: str = "USD", forcar: bool = False):
    """Ultimo boletim de fechamento disponivel da moeda."""
    df, resp = cotacao_periodo(moeda, 12, forcar)
    if df.empty:
        return None, resp
    fech = df[df["tipoBoletim"].astype(str).str.contains("Fechamento", case=False, na=False)]
    base = fech if not fech.empty else df
    return base.iloc[-1], resp


# ---------------------------------------------------------------------------
# Expectativas de mercado (Relatorio Focus)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def focus(recurso: str = "ExpectativasMercadoAnuais", indicador: str = "",
          top: int = 2000, forcar: bool = False):
    opcoes = {"$top": int(top), "$orderby": "Data desc"}
    if indicador:
        opcoes["$filter"] = "Indicador eq '%s'" % indicador
    resp = http.olinda("Expectativas", recurso, TTL_DIARIO,
                       "BCB/Focus %s" % recurso, opcoes=opcoes, forcar=forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    if "Data" in df:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df, resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def focus_indicadores(recurso: str = "ExpectativasMercadoAnuais", forcar: bool = False):
    """Lista de indicadores disponiveis no recurso, para montar o filtro."""
    resp = http.olinda("Expectativas", recurso, TTL_DIARIO,
                       "BCB/Focus indicadores %s" % recurso,
                       opcoes={"$top": 4000, "$select": "Indicador,Data",
                               "$orderby": "Data desc"}, forcar=forcar)
    if not resp.ok or not resp.dados:
        return [], resp
    return sorted({r.get("Indicador") for r in resp.dados if r.get("Indicador")}), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def focus_projecao(indicador: str, ano: str, forcar: bool = False):
    """Mediana mais recente projetada para o indicador no ano de referencia."""
    resp = http.olinda(
        "Expectativas", "ExpectativasMercadoAnuais", TTL_DIARIO,
        "BCB/Focus %s %s" % (indicador, ano),
        opcoes={"$top": 1, "$orderby": "Data desc",
                "$filter": "Indicador eq '%s' and DataReferencia eq '%s'" % (indicador, ano)},
        forcar=forcar,
    )
    if not resp.ok or not resp.dados:
        return None, resp
    return resp.dados[0], resp


# ---------------------------------------------------------------------------
# Instituicoes autorizadas a funcionar
# ---------------------------------------------------------------------------
TIPOS_INSTITUICAO = {
    "Bancos e multiplas com carteira comercial": "SedesBancoComMultCE",
    "Cooperativas de credito": "SedesCooperativas",
    "Administradoras de consorcio": "SedesConsorcios",
    "Demais sociedades autorizadas": "SedesSociedades",
}


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def instituicoes(recurso: str = "SedesBancoComMultCE", forcar: bool = False):
    resp = http.olinda("Instituicoes_em_funcionamento", recurso, TTL_CADASTRAL,
                       "BCB/Instituicoes %s" % recurso,
                       opcoes={"$top": 20000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def dominios_verificados(forcar: bool = False):
    """Dominios de internet oficialmente declarados pelas instituicoes."""
    resp = http.olinda("Instituicoes_em_funcionamento", "DominiosVerificados",
                       TTL_CADASTRAL, "BCB/Dominios verificados",
                       opcoes={"$top": 20000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# Rede de atendimento
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def agencias(uf: str = "", top: int = 20000, forcar: bool = False):
    opcoes = {"$top": int(top), "$orderby": "NomeIf"}
    if uf:
        opcoes["$filter"] = "UF eq '%s'" % uf
    resp = http.olinda("Informes_Agencias", "Agencias", TTL_CADASTRAL,
                       "BCB/Agencias %s" % (uf or "BR"), opcoes=opcoes, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def postos_atendimento(uf: str = "", top: int = 20000, forcar: bool = False):
    opcoes = {"$top": int(top)}
    if uf:
        opcoes["$filter"] = "UF eq '%s'" % uf
    resp = http.olinda("Informes_PostosDeAtendimento", "PostosAtendimento",
                       TTL_CADASTRAL, "BCB/Postos %s" % (uf or "BR"),
                       opcoes=opcoes, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def correspondentes(uf: str = "", municipio: str = "", contratante: str = "",
                    top: int = 30000, forcar: bool = False):
    filtros = []
    if uf:
        filtros.append("UF eq '%s'" % uf)
    if municipio:
        filtros.append("Municipio eq '%s'" % municipio.upper())
    if contratante:
        filtros.append("contains(NomeContratante,'%s')" % contratante.upper())
    opcoes = {"$top": int(top)}
    if filtros:
        opcoes["$filter"] = " and ".join(filtros)
    resp = http.olinda("Informes_Correspondentes", "Correspondentes", TTL_CADASTRAL,
                       "BCB/Correspondentes %s" % (uf or "BR"), opcoes=opcoes,
                       forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# Compliance - penalidades aplicadas pelo BCB
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def quadro_penalidades(recurso: str = "QuadroGeralInabilitados", forcar: bool = False):
    """recurso: QuadroGeralInabilitados ou QuadroGeralProibidos."""
    resp = http.olinda("Gepad_QuadrosGeraisInternet", recurso, TTL_CADASTRAL,
                       "BCB/%s" % recurso, opcoes={"$top": 20000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# IF.data - dados contabeis das instituicoes
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ifdata_relatorios(forcar: bool = False):
    resp = http.olinda("IFDATA", "ListaDeRelatorio", TTL_CADASTRAL,
                       "BCB/IFData relatorios", parametros={}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ifdata_cadastro(anomes: int, forcar: bool = False):
    resp = http.olinda("IFDATA", "IfDataCadastro", TTL_CADASTRAL,
                       "BCB/IFData cadastro %s" % anomes,
                       parametros={"AnoMes": int(anomes)},
                       opcoes={"$top": 5000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ifdata_valores(anomes: int, tipo_instituicao: int, relatorio: str,
                   top: int = 20000, forcar: bool = False):
    resp = http.olinda("IFDATA", "IfDataValores", TTL_CADASTRAL,
                       "BCB/IFData valores %s r%s" % (anomes, relatorio),
                       parametros={"AnoMes": int(anomes),
                                   "TipoInstituicao": int(tipo_instituicao),
                                   "Relatorio": "'%s'" % relatorio},
                       opcoes={"$top": int(top)}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# Pix
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pix_usuarios_dict(forcar: bool = False):
    """Serie de usuarios com chave cadastrada no DICT."""
    resp = http.olinda("Pix_DadosAbertos", "PixUsuariosCadastradosDICT", TTL_MENSAL,
                       "BCB/Pix usuarios DICT", opcoes={"$top": 500}, forcar=forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    df["DataGraficosPix"] = pd.to_datetime(df["DataGraficosPix"], errors="coerce")
    return df.sort_values("DataGraficosPix"), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pix_chaves(data_ref: str, forcar: bool = False):
    """Chaves por instituicao. data_ref no formato AAAA-MM-DD (fim do mes)."""
    resp = http.olinda("Pix_DadosAbertos", "ChavesPix", TTL_MENSAL,
                       "BCB/Pix chaves %s" % data_ref,
                       parametros={"Data": "'%s'" % data_ref},
                       opcoes={"$top": 60000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pix_transacoes(anomes: str, top: int = 20000, forcar: bool = False):
    """Transacoes por perfil de pagador/recebedor. anomes no formato AAAAMM."""
    resp = http.olinda("Pix_DadosAbertos", "EstatisticasTransacoesPix", TTL_MENSAL,
                       "BCB/Pix transacoes %s" % anomes,
                       parametros={"Database": "'%s'" % anomes},
                       opcoes={"$top": int(top)}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def pix_fraudes(ano: str, forcar: bool = False):
    """Estatisticas de fraude e devolucao (MED). O parametro e o ANO."""
    resp = http.olinda("Pix_DadosAbertos", "EstatisticasFraudesPix", TTL_MENSAL,
                       "BCB/Pix fraudes %s" % ano,
                       parametros={"Database": "'%s'" % ano},
                       opcoes={"$top": 500}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# SPI e STR - liquidacao
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def spi_liquidados(forcar: bool = False):
    resp = http.olinda("SPI", "PixLiquidadosAtual", TTL_DIARIO,
                       "BCB/SPI liquidados", opcoes={"$top": 4000}, forcar=forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df.sort_values("Data"), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def spi_disponibilidade(forcar: bool = False):
    resp = http.olinda("SPI", "PixDisponibilidadeSPI", TTL_DIARIO,
                       "BCB/SPI disponibilidade", opcoes={"$top": 2000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def str_liquidados(forcar: bool = False):
    resp = http.olinda("STR", "STRLiquidadosAtual", TTL_DIARIO, "BCB/STR liquidados",
                       versao="v2", opcoes={"$top": 6000}, forcar=forcar)
    if not resp.ok or not resp.dados:
        return pd.DataFrame(), resp
    df = pd.DataFrame(resp.dados)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df.sort_values("Data"), resp


# ---------------------------------------------------------------------------
# Meios de pagamento
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def meios_pagamento_mensal(anomes: str, forcar: bool = False):
    resp = http.olinda("MPV_DadosAbertos", "MeiosdePagamentosMensalDA", TTL_MENSAL,
                       "BCB/Meios de pagamento %s" % anomes,
                       parametros={"AnoMes": "'%s'" % anomes},
                       opcoes={"$top": 1000}, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# Tarifas bancarias
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def tarifas_grupos(forcar: bool = False):
    resp = http.olinda("Informes_ListaValoresDeServicoBancario", "GruposConsolidados",
                       TTL_CADASTRAL, "BCB/Tarifas grupos", forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def tarifas_valores_mercado(pessoa: str, grupo: str, forcar: bool = False):
    """Valor minimo, maximo e medio por servico. pessoa: F (fisica) ou J."""
    resp = http.olinda(
        "Informes_ListaValoresDeServicoBancario", "ListaValoresServicoBancario",
        TTL_CADASTRAL, "BCB/Tarifas mercado %s grupo %s" % (pessoa, grupo),
        parametros={"PessoaFisicaOuJuridica": "'%s'" % pessoa,
                    "CodigoGrupoConsolidado": "'%s'" % grupo},
        opcoes={"$top": 3000}, forcar=forcar,
    )
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def tarifas_instituicoes_do_grupo(grupo: str, forcar: bool = False):
    resp = http.olinda(
        "Informes_ListaTarifasPorInstituicaoFinanceira",
        "ListaInstituicoesDeGrupoConsolidado", TTL_CADASTRAL,
        "BCB/Tarifas instituicoes grupo %s" % grupo,
        parametros={"CodigoGrupoConsolidado": "'%s'" % grupo},
        opcoes={"$top": 3000, "$orderby": "Nome"}, forcar=forcar,
    )
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def tarifas_da_instituicao(pessoa: str, cnpj: str, forcar: bool = False):
    resp = http.olinda(
        "Informes_ListaTarifasPorInstituicaoFinanceira",
        "ListaTarifasPorInstituicaoFinanceira", TTL_CADASTRAL,
        "BCB/Tarifas CNPJ %s (%s)" % (cnpj, pessoa),
        parametros={"PessoaFisicaOuJuridica": "'%s'" % pessoa, "CNPJ": "'%s'" % cnpj},
        opcoes={"$top": 3000}, forcar=forcar,
    )
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# Ranking de qualidade de ouvidorias
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ouvidorias_periodos(forcar: bool = False):
    resp = http.olinda("RankingOuvidorias", "Periodos", TTL_CADASTRAL,
                       "BCB/Ouvidorias periodos",
                       opcoes={"$top": 200, "$orderby": "Ano desc,Periodo desc"},
                       forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp


@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def ouvidorias_relatorio(ano: int, periodo: int, tipo: str, forcar: bool = False):
    resp = http.olinda(
        "RankingOuvidorias", "Relatorios", TTL_CADASTRAL,
        "BCB/Ouvidorias %s-%s%s" % (ano, periodo, tipo),
        parametros={"Ano": int(ano), "Periodo": int(periodo), "TipoPeriodo": "'%s'" % tipo},
        opcoes={"$top": 3000}, forcar=forcar,
    )
    return pd.DataFrame(resp.dados or []), resp


# ---------------------------------------------------------------------------
# DASFN - catalogo das APIs de dados abertos do SFN
# ---------------------------------------------------------------------------
@st.cache_data(ttl=TTL_MEMORIA, show_spinner=False)
def dasfn_recursos(api: str = "", forcar: bool = False):
    """Catalogo oficial das APIs abertas publicadas pelas instituicoes."""
    opcoes = {"$top": 20000}
    if api:
        opcoes["$filter"] = "Api eq '%s'" % api
    resp = http.olinda("DASFN", "Recursos", TTL_CADASTRAL,
                       "BCB/DASFN %s" % (api or "todos"), opcoes=opcoes, forcar=forcar)
    return pd.DataFrame(resp.dados or []), resp
