# -*- coding: utf-8 -*-
"""Painel executivo: o retrato do dia em uma unica tela."""
import pandas as pd
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "painel"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Consultando as fontes oficiais..."):
        selic, dt_selic, r1 = bcb.ultimo_valor_sgs(432, 180, forcar)
        ipca12, dt_ipca, _ = bcb.ultimo_valor_sgs(13522, 400, forcar)
        cdi, _, _ = bcb.ultimo_valor_sgs(12, 60, forcar)
        dolar_serie, r_dolar = bcb.serie_sgs(1, 180, forcar)
        proj_ipca, _ = bcb.focus_projecao("IPCA", str(pd.Timestamp.today().year), forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], r1, atualizar, destino=topo)

    if not ui.verificar(r1, "indicadores economicos"):
        return

    # ---- indicadores do dia ----
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Selic - meta Copom",
                  "%s%%" % ui.num(selic, 2) if selic is not None else "-",
                  help="Ultima definicao do Copom em %s."
                       % (dt_selic.strftime("%d/%m/%Y") if dt_selic else "-"))
    with c2:
        st.metric("IPCA - 12 meses",
                  "%s%%" % ui.num(ipca12, 2) if ipca12 is not None else "-",
                  help="Inflacao acumulada nos ultimos 12 meses, referencia %s."
                       % (dt_ipca.strftime("%m/%Y") if dt_ipca else "-"))
    with c3:
        if not dolar_serie.empty:
            atual = float(dolar_serie.iloc[-1]["valor"])
            anterior = float(dolar_serie.iloc[-2]["valor"]) if len(dolar_serie) > 1 else atual
            variacao = ((atual / anterior) - 1) * 100 if anterior else 0
            st.metric("Dolar (PTAX venda)", "R$ %s" % ui.num(atual, 4),
                      delta="%s%%" % ui.num(variacao, 2),
                      help="Fechamento de %s."
                           % dolar_serie.iloc[-1]["data"].strftime("%d/%m/%Y"))
        else:
            st.metric("Dolar (PTAX venda)", "-")
    with c4:
        if proj_ipca:
            st.metric("IPCA projetado (Focus)",
                      "%s%%" % ui.num(proj_ipca.get("Mediana"), 2),
                      help="Mediana das projecoes do mercado para o ano corrente, "
                           "coletada em %s por %s instituicoes."
                           % (proj_ipca.get("Data", "-"),
                              proj_ipca.get("numeroRespondentes", "-")))
        else:
            st.metric("IPCA projetado (Focus)", "-")

    st.write("")

    # ---- graficos ----
    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("##### Dolar PTAX - ultimos 6 meses")
        if not dolar_serie.empty:
            ui.grafico_linhas(
                dolar_serie.set_index("data")[["valor"]].rename(
                    columns={"valor": "Dolar (R$)"}), altura=260)
        else:
            ui.vazio("Serie de cambio indisponivel no momento.")
    with dir_:
        st.markdown("##### Selic x IPCA 12 meses - 3 anos")
        selic_hist, _ = bcb.serie_sgs(432, 1100, forcar)
        ipca_hist, _ = bcb.serie_sgs(13522, 1100, forcar)
        if not selic_hist.empty and not ipca_hist.empty:
            comparativo = pd.merge(
                selic_hist.rename(columns={"valor": "Selic (% a.a.)"}),
                ipca_hist.rename(columns={"valor": "IPCA 12m (%)"}),
                on="data", how="outer",
            ).sort_values("data").set_index("data").ffill()
            ui.grafico_linhas(comparativo, altura=260, titulo_y="%")
        else:
            ui.vazio("Series indisponiveis no momento.")

    # ---- Pix ----
    st.markdown("##### Pix - valores liquidados no SPI")
    spi, r_spi = bcb.spi_liquidados(forcar)
    if not spi.empty:
        recente = spi.tail(90).copy()
        a, b, c = st.columns(3)
        ultimo = recente.iloc[-1]
        with a:
            st.metric("Transacoes no ultimo dia apurado",
                      ui.inteiro(ultimo["Quantidade"]),
                      help="Referencia: %s" % ultimo["Data"].strftime("%d/%m/%Y"))
        with b:
            st.metric("Valor medio por transacao", ui.moeda(ultimo["Media"]))
        with c:
            st.metric("Media diaria (90 dias)", ui.inteiro(recente["Quantidade"].mean()))
        st.bar_chart(recente.set_index("Data")["Quantidade"], height=220,
                     color="#0EA5E9")
        st.caption(r_spi.selo())
    else:
        ui.vazio("Estatisticas do SPI indisponiveis no momento.")

    ui.nota(
        "Todos os numeros desta tela vem direto das APIs publicas do Banco Central. "
        "O sistema revalida cada fonte automaticamente conforme a periodicidade do "
        "dado e mantem a ultima copia boa caso a fonte fique fora do ar."
    )
