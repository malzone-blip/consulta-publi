# -*- coding: utf-8 -*-
"""Comparativo entre os meios de pagamento do varejo."""
from datetime import date

import pandas as pd
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "meios_pagamento"

INSTRUMENTOS = {
    "Pix": ("quantidadePix", "valorPix"),
    "TED": ("quantidadeTED", "valorTED"),
    "Boleto": ("quantidadeBoleto", "valorBoleto"),
    "Cheque": ("quantidadeCheque", "valorCheque"),
    "DOC": ("quantidadeDOC", "valorDOC"),
    "TEC": ("quantidadeTEC", "valorTEC"),
}


def _meses(quantidade: int = 24):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(quantidade):
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
        saida.append("%d%02d" % (ano, mes))
    return saida


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    # A base de meios de pagamento sai com dois a tres meses de defasagem; abrir
    # no mes anterior mostraria "sem dados" para todo mundo. O padrao aponta
    # para o mes mais recente que costuma estar publicado.
    anomes = st.selectbox(
        "Mes de referencia", _meses(), index=2,
        format_func=lambda m: "%s/%s" % (m[4:], m[:4]),
        help="A consulta devolve o conjunto publicado a partir dessa data-base. "
             "Meses muito recentes ainda nao foram divulgados pelo Banco Central.",
    )

    with st.spinner("Carregando meios de pagamento..."):
        df, resp = bcb.meios_pagamento_mensal(anomes, forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "meios de pagamento"):
        return
    if df.empty:
        ui.vazio("Sem dados para esse mes. A serie e publicada com defasagem - "
                 "escolha um mes anterior.")
        return

    df = df.sort_values("AnoMes")
    ultimo = df.iloc[-1]

    linhas = []
    for nome, (col_qtd, col_val) in INSTRUMENTOS.items():
        if col_qtd in df.columns:
            linhas.append({
                "Instrumento": nome,
                "Quantidade (mil)": float(ultimo.get(col_qtd) or 0),
                "Valor (R$ mi)": float(ultimo.get(col_val) or 0),
            })
    resumo = pd.DataFrame(linhas)
    total_qtd = resumo["Quantidade (mil)"].sum()
    resumo["Participacao (%)"] = resumo["Quantidade (mil)"] / max(total_qtd, 1) * 100
    resumo = resumo.sort_values("Quantidade (mil)", ascending=False)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Mes apurado", "%s/%s" % (str(ultimo["AnoMes"])[4:],
                                            str(ultimo["AnoMes"])[:4]))
    with c2:
        lider = resumo.iloc[0]
        st.metric("Instrumento mais usado", lider["Instrumento"],
                  delta="%s%% das operacoes" % ui.num(lider["Participacao (%)"], 1))
    with c3:
        st.metric("Operacoes no mes (todas)", ui.num(total_qtd, 0) + " mil")

    st.write("")
    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("##### Participacao por quantidade")
        st.bar_chart(resumo.set_index("Instrumento")["Quantidade (mil)"],
                     height=300, horizontal=True, color="#2563EB")
    with dir_:
        st.markdown("##### Participacao por valor")
        st.bar_chart(resumo.set_index("Instrumento")["Valor (R$ mi)"],
                     height=300, horizontal=True, color="#0EA5E9")

    ui.tabela(resumo, "meios_pagamento_%s" % anomes, altura=280, config={
        "Quantidade (mil)": st.column_config.NumberColumn(format="%.0f"),
        "Valor (R$ mi)": st.column_config.NumberColumn(format="%.0f"),
        "Participacao (%)": st.column_config.ProgressColumn(
            "Participacao", format="%.1f%%", min_value=0, max_value=100),
    })

    if len(df) > 1:
        st.markdown("##### Evolucao dentro da base retornada")
        serie = df.copy()
        serie["Mes"] = serie["AnoMes"].astype(str)
        colunas = [c for c, _ in INSTRUMENTOS.values() if c in serie.columns]
        st.line_chart(serie.set_index("Mes")[colunas].rename(
            columns={v[0]: k for k, v in INSTRUMENTOS.items()}), height=280)

    ui.nota(
        "Valores publicados pelo Banco Central em milhares de operacoes e milhoes "
        "de reais. A comparacao por quantidade mostra o habito do consumidor; a "
        "comparacao por valor mostra para onde vai o dinheiro de fato."
    )
