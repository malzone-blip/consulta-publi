# -*- coding: utf-8 -*-
"""Series economicas do SGS - Banco Central."""
import pandas as pd
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "indicadores"

PERIODOS = {"6 meses": 180, "1 ano": 365, "2 anos": 730,
            "5 anos": 1825, "10 anos": 3650}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2 = st.columns([0.62, 0.38])
    with f1:
        nomes = st.multiselect(
            "Series", list(bcb.SERIES_SGS.keys()),
            default=["Selic - meta definida pelo Copom (% a.a.)",
                     "IPCA - acumulado 12 meses (%)"],
            help="Selecione uma ou mais series para comparar no mesmo grafico.",
        )
    with f2:
        periodo = st.select_slider("Periodo", list(PERIODOS.keys()), value="2 anos")

    if not nomes:
        ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)
        ui.vazio("Selecione ao menos uma serie para visualizar.")
        return

    dias = PERIODOS[periodo]
    quadros, resposta = {}, None
    with st.spinner("Buscando series no Banco Central..."):
        for nome in nomes:
            codigo = bcb.SERIES_SGS[nome]["codigo"]
            df, resp = bcb.serie_sgs(codigo, dias, forcar)
            resposta = resposta or resp
            if not df.empty:
                quadros[nome] = df.set_index("data")["valor"]

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resposta, atualizar, destino=topo)
    if not ui.verificar(resposta, "series do SGS"):
        return
    if not quadros:
        ui.vazio("As series selecionadas nao retornaram dados no periodo.")
        return

    consolidado = pd.DataFrame(quadros).sort_index()

    # Resumo por serie
    colunas = st.columns(min(len(quadros), 4))
    for i, (nome, serie) in enumerate(quadros.items()):
        limpa = serie.dropna()
        if limpa.empty:
            continue
        with colunas[i % len(colunas)]:
            atual = float(limpa.iloc[-1])
            primeiro = float(limpa.iloc[0])
            delta = atual - primeiro
            st.metric(
                nome.split(" - ")[0], ui.num(atual, 4 if abs(atual) < 10 else 2),
                delta="%s no periodo" % ui.num(delta, 2),
                help="Ultimo ponto em %s. Fonte: SGS serie %d."
                     % (limpa.index[-1].strftime("%d/%m/%Y"),
                        bcb.SERIES_SGS[nome]["codigo"]),
            )

    st.write("")
    ui.grafico_linhas(consolidado.ffill(), altura=380)

    with st.expander("Ver dados detalhados", icon=":material/table_view:"):
        tabela = consolidado.reset_index().rename(columns={"data": "Data"})
        tabela["Data"] = tabela["Data"].dt.strftime("%d/%m/%Y")
        ui.tabela(tabela.sort_values("Data", ascending=False), "series_sgs")

    ui.nota(
        "Fonte: Sistema Gerenciador de Series Temporais (SGS) do Banco Central. "
        "Cada serie tem periodicidade propria - series mensais so mudam de valor "
        "na virada do mes de referencia."
    )
