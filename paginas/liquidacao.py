# -*- coding: utf-8 -*-
"""SPI e STR: liquidacao de pagamentos instantaneos e de reservas."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "liquidacao"

JANELAS = {"90 dias": 90, "180 dias": 180, "1 ano": 365, "Tudo": 100000}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    janela = st.select_slider("Janela", list(JANELAS.keys()), value="180 dias")
    limite = JANELAS[janela]

    with st.spinner("Carregando dados de liquidacao..."):
        spi, r_spi = bcb.spi_liquidados(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], r_spi, atualizar, destino=topo)
    if not ui.verificar(r_spi, "SPI"):
        return

    aba_spi, aba_str, aba_disp = st.tabs(
        ["SPI - Pix", "STR - Reservas", "Disponibilidade do SPI"])

    with aba_spi:
        if spi.empty:
            ui.vazio("Sem dados do SPI.")
        else:
            recorte = spi.tail(limite)
            ultimo = recorte.iloc[-1]
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Transacoes no ultimo dia", ui.inteiro(ultimo["Quantidade"]),
                          help="Referencia: %s" % ultimo["Data"].strftime("%d/%m/%Y"))
            with c2:
                st.metric("Valor total no dia",
                          ui.moeda(ultimo["Total"] / 1000) + " bi",
                          help="Valores publicados em milhoes de reais.")
            with c3:
                st.metric("Ticket medio", ui.moeda(ultimo["Media"]))
            with c4:
                st.metric("Pico de transacoes na janela",
                          ui.inteiro(recorte["Quantidade"].max()))

            st.markdown("##### Quantidade de transacoes por dia")
            st.bar_chart(recorte.set_index("Data")["Quantidade"], height=280,
                         color="#2563EB")
            st.markdown("##### Valor liquidado por dia (R$ milhoes)")
            st.area_chart(recorte.set_index("Data")["Total"], height=240,
                          color="#0EA5E9")

            exibir = recorte.copy()
            exibir["Data"] = exibir["Data"].dt.strftime("%d/%m/%Y")
            ui.tabela(exibir.rename(columns={
                "Quantidade": "Transacoes", "CanalPrimario": "Canal primario",
                "CanalSecundario": "Canal secundario",
                "Total": "Valor (R$ mi)", "Media": "Ticket medio (R$)"}),
                "spi_liquidados", altura=320)

    with aba_str:
        with st.spinner("Carregando STR..."):
            df_str, r_str = bcb.str_liquidados(forcar)
        if ui.verificar(r_str, "STR") and not df_str.empty:
            recorte = df_str.tail(limite)
            ultimo = recorte.iloc[-1]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Operacoes no ultimo dia", ui.inteiro(ultimo["Quantidade"]),
                          help="Referencia: %s" % ultimo["Data"].strftime("%d/%m/%Y"))
            with c2:
                st.metric("Valor liquidado", ui.moeda(ultimo["Total"] / 1_000_000_000)
                          + " bi")
            with c3:
                st.metric("Valor medio por operacao", ui.moeda(ultimo["Media"]))
            st.markdown("##### Operacoes liquidadas no STR")
            st.bar_chart(recorte.set_index("Data")["Quantidade"], height=280,
                         color="#1E40AF")
            st.caption(r_str.selo())
        elif df_str.empty:
            ui.vazio("Sem dados do STR.")

    with aba_disp:
        with st.spinner("Carregando disponibilidade..."):
            disp, r_disp = bcb.spi_disponibilidade(forcar)
        if ui.verificar(r_disp, "disponibilidade do SPI"):
            if disp.empty:
                ui.vazio("Sem registros de disponibilidade.")
            else:
                ui.tabela(disp, "spi_disponibilidade", altura=420)
                ui.nota(
                    "Disponibilidade e o percentual de tempo em que o Sistema de "
                    "Pagamentos Instantaneos esteve operante. Interrupcoes do SPI "
                    "afetam todos os bancos ao mesmo tempo."
                )
