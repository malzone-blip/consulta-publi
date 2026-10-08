# -*- coding: utf-8 -*-
"""Expectativas de mercado - Relatorio Focus."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "focus"

RECURSOS = {
    "Projecoes anuais": "ExpectativasMercadoAnuais",
    "Projecoes mensais": "ExpectativaMercadoMensais",
    "Projecoes trimestrais": "ExpectativasMercadoTrimestrais",
    "Selic (por reuniao do Copom)": "ExpectativasMercadoSelic",
    "Inflacao 12 meses a frente": "ExpectativasMercadoInflacao12Meses",
    "Top 5 - projecoes anuais": "ExpectativasMercadoTop5Anuais",
}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2 = st.columns([0.45, 0.55])
    with f1:
        rotulo = st.selectbox("Tipo de projecao", list(RECURSOS.keys()))
    recurso = RECURSOS[rotulo]

    with st.spinner("Consultando o Focus..."):
        indicadores, _ = bcb.focus_indicadores(recurso, forcar)
    with f2:
        indicador = st.selectbox(
            "Indicador", ["(todos)"] + list(indicadores),
            help="Lista extraida da propria API, ja refletindo o boletim mais recente.",
        )

    filtro = "" if indicador == "(todos)" else indicador
    with st.spinner("Carregando projecoes..."):
        df, resp = bcb.focus(recurso, filtro, 3000, forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "expectativas de mercado"):
        return
    if df.empty:
        ui.vazio("Nenhuma projecao retornada para esse filtro.")
        return

    # Ultima coleta divulgada
    ultima = df["Data"].max()
    recente = df[df["Data"] == ultima].copy()

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Coleta mais recente", ultima.strftime("%d/%m/%Y"))
    with c2:
        st.metric("Projecoes na coleta", ui.inteiro(len(recente)))
    with c3:
        if "numeroRespondentes" in recente:
            st.metric("Instituicoes respondentes",
                      ui.inteiro(recente["numeroRespondentes"].max()))

    st.write("")
    st.markdown("##### Projecoes da coleta mais recente")

    colunas_saida = [c for c in ("Indicador", "IndicadorDetalhe", "DataReferencia",
                                 "Mediana", "Media", "DesvioPadrao", "Minimo",
                                 "Maximo", "numeroRespondentes")
                     if c in recente.columns]
    exibir = recente[colunas_saida].sort_values(
        [c for c in ("Indicador", "DataReferencia") if c in colunas_saida]
    )
    ui.tabela(
        exibir, "focus_%s" % recurso, altura=340,
        config={
            "Mediana": st.column_config.NumberColumn("Mediana", format="%.2f"),
            "Media": st.column_config.NumberColumn("Media", format="%.2f"),
            "DesvioPadrao": st.column_config.NumberColumn("Desvio padrao", format="%.3f"),
            "Minimo": st.column_config.NumberColumn("Minimo", format="%.2f"),
            "Maximo": st.column_config.NumberColumn("Maximo", format="%.2f"),
            "numeroRespondentes": st.column_config.NumberColumn("Respondentes",
                                                                format="%d"),
            "DataReferencia": st.column_config.TextColumn("Referencia"),
        },
    )

    # Evolucao da mediana ao longo das coletas
    if filtro and "DataReferencia" in df.columns:
        st.markdown("##### Como a projecao mudou ao longo das coletas")
        referencias = sorted(df["DataReferencia"].dropna().unique().tolist())
        escolha = st.selectbox("Periodo de referencia", referencias,
                               index=max(0, len(referencias) - 1))
        serie = (df[df["DataReferencia"] == escolha]
                 .sort_values("Data").set_index("Data")["Mediana"])
        if not serie.empty:
            ui.grafico_linhas(serie.to_frame("Mediana projetada"), altura=280)
            st.caption(
                "Mediana das projecoes para %s, coleta a coleta. Fonte: Focus/BCB."
                % escolha
            )

    ui.nota(
        "O Focus e divulgado as segundas-feiras com a coleta encerrada na sexta "
        "anterior. O sistema revalida a fonte a cada 6 horas, entao a nova coleta "
        "aparece aqui sozinha assim que o Banco Central publica."
    )
