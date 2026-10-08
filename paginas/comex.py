# -*- coding: utf-8 -*-
"""Comercio exterior: balanca comercial por pais, NCM e UF (ComexStat)."""
from datetime import date

import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import comex

CHAVE = "comex"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    ano_atual = date.today().year
    f1, f2, f3, f4 = st.columns([0.24, 0.22, 0.22, 0.32])
    with f1:
        fluxo = st.selectbox("Fluxo", list(comex.FLUXOS.keys()),
                             format_func=lambda k: comex.FLUXOS[k])
    with f2:
        ano_de = st.selectbox("De (ano)", list(range(ano_atual, 2010, -1)), index=0)
    with f3:
        ano_ate = st.selectbox("Ate (ano)", list(range(ano_atual, 2010, -1)), index=0)
    with f4:
        recorte = st.selectbox("Detalhar por", list(comex.RECORTES.keys()),
                               format_func=lambda k: comex.RECORTES[k])

    de = "%d-01" % min(ano_de, ano_ate)
    ate = "%d-12" % max(ano_de, ano_ate)

    with st.spinner("Consultando o ComexStat..."):
        df, resp = comex.balanca(fluxo, de, ate, (recorte,), forcar=forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "ComexStat"):
        return
    if df.empty:
        ui.vazio("Sem dados para o recorte selecionado.")
        return

    total_fob = df["metricFOB"].sum() if "metricFOB" in df else 0
    total_kg = df["metricKG"].sum() if "metricKG" in df else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Valor FOB total", "US$ %s" % ui.num(total_fob / 1_000_000, 1) + " mi")
    with c2:
        st.metric("Peso total", "%s t" % ui.num(total_kg / 1000, 0))
    with c3:
        st.metric("Linhas retornadas", ui.inteiro(len(df)))

    rotulo_dim = comex.RECORTES[recorte].split(" ")[0]
    coluna_dim = next((c for c in df.columns
                       if c not in ("metricFOB", "metricKG", "metricStatistic",
                                    "year", "monthNumber", "month")), df.columns[0])

    if "metricFOB" in df:
        st.markdown("##### Maiores valores FOB por %s" % rotulo_dim.lower())
        top = (df.groupby(coluna_dim)["metricFOB"].sum()
               .sort_values().tail(15))
        st.bar_chart(top, height=340, horizontal=True, color="#2563EB")

    exibir = df.copy()
    renomear = {coluna_dim: rotulo_dim, "metricFOB": "Valor FOB (US$)",
                "metricKG": "Peso (kg)", "year": "Ano"}
    exibir = exibir.rename(columns=renomear)
    ui.tabela(exibir, "comex_%s_%s" % (fluxo, recorte), altura=420, config={
        "Valor FOB (US$)": st.column_config.NumberColumn(format="%.0f"),
        "Peso (kg)": st.column_config.NumberColumn(format="%.0f"),
    })

    ui.nota(
        "Fonte: ComexStat / MDIC, estatisticas oficiais de comercio exterior. "
        "Valor FOB e o valor da mercadoria sem frete e seguro. A serie e mensal e "
        "sai com poucas semanas de defasagem sobre o mes encerrado."
    )
