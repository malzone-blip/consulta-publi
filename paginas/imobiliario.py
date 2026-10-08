# -*- coding: utf-8 -*-
"""Mercado imobiliario: indices de reajuste e localizacao."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import bcb, externas, localizacao

CHAVE = "imobiliario"

# Indices que reajustam aluguel e obra (codigos SGS verificados).
INDICES = {
    "IGP-M (reajuste de aluguel)": {"codigo": 189, "unidade": "%"},
    "IPCA (reajuste alternativo)": {"codigo": 433, "unidade": "%"},
    "INCC (custo de construcao)": {"codigo": 192, "unidade": "%"},
    "IGP-DI": {"codigo": 190, "unidade": "%"},
}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    aba_indices, aba_reajuste, aba_local = st.tabs(
        ["Indices", "Simular reajuste", "Localizar endereco"])

    with aba_indices:
        escolha = st.multiselect(
            "Indices", list(INDICES.keys()),
            default=["IGP-M (reajuste de aluguel)", "INCC (custo de construcao)"])
        if escolha:
            quadros, resp = {}, None
            with st.spinner("Carregando indices..."):
                for nome in escolha:
                    df, r = bcb.serie_sgs(INDICES[nome]["codigo"], 1825, forcar)
                    resp = resp or r
                    if not df.empty:
                        quadros[nome] = df.set_index("data")["valor"]
            if ui.verificar(resp, "indices") and quadros:
                import pandas as pd
                consolidado = pd.DataFrame(quadros).sort_index()
                colunas = st.columns(len(quadros))
                for i, (nome, serie) in enumerate(quadros.items()):
                    with colunas[i]:
                        limpa = serie.dropna()
                        acum12 = ((limpa.tail(12) / 100 + 1).prod() - 1) * 100 \
                            if len(limpa) >= 12 else None
                        st.metric(nome.split(" (")[0],
                                  "%s%% no mes" % ui.num(limpa.iloc[-1], 2),
                                  delta="%s%% em 12m" % ui.num(acum12, 2)
                                  if acum12 is not None else None)
                ui.grafico_linhas(consolidado.ffill(), altura=320, titulo_y="% ao mes")
                st.caption(resp.selo())

    with aba_reajuste:
        st.caption("Calcula o reajuste acumulado de um indice entre dois pontos - "
                   "util para renovar aluguel ou contrato indexado.")
        c1, c2, c3 = st.columns(3)
        with c1:
            indice = st.selectbox("Indice", list(INDICES.keys()), key="reaj_indice")
        with c2:
            valor = st.number_input("Valor atual (R$)", min_value=0.0, value=1000.0,
                                    step=100.0)
        with c3:
            meses = st.selectbox("Periodo", [12, 24, 36], key="reaj_meses",
                                 format_func=lambda m: "%d meses" % m)
        df, r = bcb.serie_sgs(INDICES[indice]["codigo"], 1825, forcar)
        if not df.empty:
            janela = df.tail(meses)
            fator = (janela["valor"] / 100 + 1).prod()
            acumulado = (fator - 1) * 100
            novo = valor * fator
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Acumulado no periodo", "%s%%" % ui.num(acumulado, 2))
            with m2:
                st.metric("Valor reajustado", ui.moeda(novo))
            with m3:
                st.metric("Diferenca", ui.moeda(novo - valor))
            st.caption("Base: %s, ultimos %d meses ate %s."
                       % (indice, meses, janela.iloc[-1]["data"].strftime("%m/%Y")))

    with aba_local:
        st.caption("Converte um endereco em coordenadas (OpenStreetMap) e mostra o "
                   "ponto no mapa. Use para localizar imoveis, filiais ou garantias.")
        endereco = st.text_input("Endereco",
                                 placeholder="Ex.: Avenida Paulista 1000, Sao Paulo")
        if st.button("Localizar", type="primary", icon=":material/location_on:") \
                and endereco.strip():
            with st.spinner("Consultando..."):
                pontos, erro = localizacao.geocodificar(endereco.strip())
            audit.registrar(auth.usuario_atual()["usuario"], "GEOCODIFICACAO",
                            "endereco=%s" % endereco.strip()[:80])
            if erro:
                st.error(erro, icon=":material/error:")
            elif not pontos:
                st.warning("Endereco nao localizado. Tente detalhar mais.",
                           icon=":material/wrong_location:")
            else:
                p = pontos[0]
                st.success(p["nome"], icon=":material/place:")
                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Latitude", ui.num(p["lat"], 6))
                with c2:
                    st.metric("Longitude", ui.num(p["lon"], 6))
                import pandas as pd
                st.map(pd.DataFrame([{"lat": p["lat"], "lon": p["lon"]}]), zoom=15)

    ui.nota(
        "Aluguel costuma ser reajustado pelo IGP-M; obras acompanham o INCC. Os "
        "indices vem do Banco Central. A localizacao usa o OpenStreetMap "
        "(Nominatim), gratuito, com limite de uma consulta por segundo."
    )
