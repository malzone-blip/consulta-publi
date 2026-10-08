# -*- coding: utf-8 -*-
"""Companhias abertas e fundos de investimento (CVM)."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import fiscal

CHAVE = "cvm"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    # A pagina tem 2 abas com fontes distintas; o cabecalho fica neutro e cada
    # aba mostra o proprio selo de procedencia.
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    aba_cvm, aba_fundos = st.tabs(["Companhias abertas", "Fundos de investimento"])

    with aba_cvm:
        _aba_companhias(forcar)
    with aba_fundos:
        _aba_fundos(forcar)


def _aba_companhias(forcar):
    with st.spinner("Carregando cadastro da CVM..."):
        dfv, respv = fiscal.companhias_abertas(forcar)
    if respv is not None:
        ui.selo(respv)
    if not ui.verificar(respv, "companhias abertas"):
        return
    if dfv.empty:
        ui.vazio()
        return

    col_situacao = "SIT" if "SIT" in dfv else None
    ativas = dfv
    if col_situacao:
        ativas = dfv[dfv[col_situacao].astype(str).str.upper()
                     .str.contains("ATIVO", na=False)]
    busca = st.text_input("Buscar companhia (nome ou CNPJ)",
                          key="busca_cvm", placeholder="Ex.: PETROBRAS")
    base = dfv
    if busca:
        alvo = busca.strip().upper()
        dig = "".join(c for c in alvo if c.isdigit())
        col_nome = next((c for c in ("DENOM_SOCIAL", "DENOM_COMERC")
                         if c in dfv), None)
        mascara = (dfv[col_nome].astype(str).str.upper().str.contains(
            alvo, na=False) if col_nome
            else pd.Series(False, index=dfv.index))
        if dig and "CNPJ_CIA" in dfv:
            mascara = mascara | dfv["CNPJ_CIA"].astype(str).str.replace(
                r"\D", "", regex=True).str.contains(dig, na=False)
        base = dfv[mascara]
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Companhias no cadastro", ui.inteiro(len(dfv)))
    with c2:
        st.metric("Situacao ativa", ui.inteiro(len(ativas)))
    ui.tabela(base, "cvm_companhias", altura=420)
    ui.nota(
        "Cadastro oficial das companhias abertas registradas na CVM. "
        "E a porta de entrada para as demonstracoes financeiras (DFP/ITR) "
        "e os fatos relevantes de cada empresa listada."
    )


def _aba_fundos(forcar):
    with st.spinner("Carregando o cadastro de fundos da CVM (~18 MB na 1a vez)..."):
        cad, resp = fiscal.fundos_cadastro(forcar)
    if not ui.verificar(resp, "cadastro de fundos"):
        return
    if cad.empty:
        ui.vazio("Cadastro de fundos indisponivel.")
        return

    situacoes = sorted(cad["SIT"].dropna().unique().tolist()) if "SIT" in cad else []
    c1, c2 = st.columns([0.62, 0.38])
    with c1:
        busca = st.text_input("Buscar fundo (nome ou CNPJ)", key="busca_fundo",
                              placeholder="Ex.: dividendos, 00.000.000/0001-00")
    with c2:
        situacao = st.selectbox("Situacao", ["(todas)"] + situacoes, key="sit_fundo")

    filtrado = fiscal.filtrar_fundos(
        cad, busca, "" if situacao == "(todas)" else situacao)

    m1, m2 = st.columns(2)
    with m1:
        st.metric("Fundos no cadastro", ui.inteiro(len(cad)))
    with m2:
        st.metric("Exibidos", ui.inteiro(len(filtrado)))
    st.caption(resp.selo())

    colunas = [c for c in ("CNPJ_FUNDO", "DENOM_SOCIAL", "SIT", "CLASSE",
                           "DT_INI_ATIV") if c in filtrado.columns]
    exibir = filtrado[colunas].rename(columns={
        "CNPJ_FUNDO": "CNPJ", "DENOM_SOCIAL": "Fundo", "SIT": "Situacao",
        "CLASSE": "Classe", "DT_INI_ATIV": "Inicio"}) if colunas else filtrado
    ui.tabela(exibir, "cvm_fundos", altura=340)

    # Informe diario de um fundo especifico
    st.markdown("##### Cota e patrimonio diario de um fundo")
    st.caption("Escolha um fundo (busque acima para reduzir a lista) e um mes para "
               "ver a evolucao diaria da cota, do patrimonio e da captacao.")
    if filtrado.empty or "CNPJ_FUNDO" not in filtrado:
        return
    opcoes = filtrado.head(300)
    mapa = {r["CNPJ_FUNDO"]: (r.get("DENOM_SOCIAL") or r["CNPJ_FUNDO"])[:70]
            for _, r in opcoes.iterrows()}
    cc1, cc2 = st.columns([0.62, 0.38])
    with cc1:
        escolha = st.selectbox("Fundo (da busca acima)", list(mapa.keys()),
                               format_func=lambda c: mapa[c], key="fundo_inf")
    with cc2:
        meses = _meses_informe()
        anomes = st.selectbox("Mes", meses,
                              format_func=lambda m: "%s/%s" % (m[4:], m[:4]),
                              key="mes_inf_fundo")
    cnpj_digitado = st.text_input(
        "Ou informe o CNPJ da classe diretamente (opcional)",
        placeholder="Use se tiver o CNPJ exato do extrato - regime FIF",
        help="Desde a Resolucao CVM 175, o informe diario e por classe do fundo. "
             "Se o fundo escolhido nao retornar dados, cole aqui o CNPJ que consta "
             "no seu extrato.")
    cnpj_fundo = cnpj_digitado.strip() or escolha

    if st.button("Carregar informe diario", icon=":material/query_stats:"):
        with st.spinner("Lendo o informe diario (pode levar alguns segundos)..."):
            inf, erro = fiscal.informe_diario_fundo(cnpj_fundo, anomes, forcar)
        if erro:
            st.error(erro, icon=":material/error:")
        elif inf.empty:
            ui.vazio("Sem lancamentos para esse fundo nesse mes.")
        else:
            ult = inf.iloc[-1]
            a, b, c = st.columns(3)
            with a:
                st.metric("Cota mais recente", ui.moeda(ult.get("VL_QUOTA"), "R$", 6))
            with b:
                st.metric("Patrimonio liquido",
                          ui.moeda(ult.get("VL_PATRIM_LIQ", 0) / 1_000_000) + " mi")
            with c:
                st.metric("Cotistas", ui.inteiro(ult.get("NR_COTST"))
                          if "NR_COTST" in inf else "-")
            if "DT_COMPTC" in inf and "VL_QUOTA" in inf:
                serie = inf.set_index("DT_COMPTC")[["VL_QUOTA"]].rename(
                    columns={"VL_QUOTA": "Valor da cota (R$)"})
                ui.grafico_linhas(serie, altura=280, titulo_y="R$")
            exibir_inf = inf.copy()
            if "DT_COMPTC" in exibir_inf:
                exibir_inf["DT_COMPTC"] = exibir_inf["DT_COMPTC"].dt.strftime("%d/%m/%Y")
            ui.tabela(exibir_inf, "informe_%s_%s" % (cnpj_fundo, anomes), altura=280)

    ui.nota(
        "Fonte: dados abertos de fundos da CVM. O cadastro lista todos os fundos; o "
        "informe diario traz cota, patrimonio e captacao dia a dia. O informe do mes "
        "e um arquivo grande - o sistema baixa uma vez e filtra pelo fundo escolhido."
    )


def _meses_informe(quantidade=12):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(quantidade):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        saida.append("%d%02d" % (ano, mes))
    return saida
