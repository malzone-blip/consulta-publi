# -*- coding: utf-8 -*-
"""Contas publicas de estados e municipios - SICONFI (Tesouro Nacional)."""
from datetime import date

import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import governo

CHAVE = "contas_publicas"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    with st.spinner("Carregando entes federativos..."):
        entes, r_entes = governo.entes(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], r_entes, atualizar,
                 destino=topo)
    if not ui.verificar(r_entes, "entes do SICONFI"):
        return
    if entes.empty:
        ui.vazio("Nao foi possivel carregar a lista de entes.")
        return

    # Filtro de ente: UF -> ente
    ufs = sorted(entes["uf"].dropna().unique().tolist()) if "uf" in entes else []
    f1, f2, f3 = st.columns([0.18, 0.46, 0.36])
    with f1:
        uf = st.selectbox("UF", ufs, index=ufs.index("SP") if "SP" in ufs else 0)
    entes_uf = entes[entes["uf"] == uf] if "uf" in entes else entes
    # Inclui o proprio estado (esfera E) e municipios (esfera M)
    mapa = {}
    for _, r in entes_uf.sort_values("ente").iterrows():
        esfera = r.get("esfera", "")
        rotulo = "%s%s" % (r.get("ente", ""),
                           "  (Estado)" if esfera == "E" else "")
        mapa[str(r.get("cod_ibge"))] = (rotulo, esfera)
    with f2:
        cod = st.selectbox("Ente", list(mapa.keys()),
                           format_func=lambda c: mapa[c][0])
    with f3:
        exercicio = st.selectbox("Exercicio", list(range(date.today().year, 2014, -1)),
                                 index=1)

    esfera = mapa[cod][1] or "M"
    aba_rreo, aba_rgf = st.tabs(["RREO - execucao orcamentaria",
                                 "RGF - gestao fiscal"])

    with aba_rreo:
        c1, c2 = st.columns(2)
        with c1:
            periodo = st.selectbox("Bimestre", [1, 2, 3, 4, 5, 6], key="rreo_bim",
                                   format_func=lambda p: "%do bimestre" % p)
        with c2:
            anexo = st.selectbox("Anexo", governo.ANEXOS_RREO, key="rreo_anexo")
        with st.spinner("Consultando o SICONFI..."):
            df, resp = governo.rreo(exercicio, periodo, anexo, esfera, cod, forcar)
        if ui.verificar(resp, "RREO"):
            _mostrar(df, "rreo_%s_%s" % (cod, exercicio))

    with aba_rgf:
        c1, c2 = st.columns(2)
        with c1:
            quad = st.selectbox("Quadrimestre", [1, 2, 3], key="rgf_quad",
                                format_func=lambda p: "%do quadrimestre" % p)
        with c2:
            anexo_g = st.selectbox("Anexo", governo.ANEXOS_RGF, key="rgf_anexo")
        with st.spinner("Consultando o SICONFI..."):
            dfg, respg = governo.rgf(exercicio, quad, anexo_g, esfera, cod, "E", forcar)
        if ui.verificar(respg, "RGF"):
            _mostrar(dfg, "rgf_%s_%s" % (cod, exercicio))

    ui.nota(
        "SICONFI e a base oficial de contas publicas do Tesouro Nacional. O RREO "
        "mostra a execucao do orcamento bimestre a bimestre; o RGF acompanha os "
        "limites da Lei de Responsabilidade Fiscal (pessoal, divida). Util para "
        "avaliar a saude financeira de um ente antes de um contrato ou convenio."
    )


def _mostrar(df, nome):
    if df.empty:
        ui.vazio("O SICONFI nao retornou dados para essa combinacao. O ente pode "
                 "nao ter enviado a declaracao desse periodo.")
        return
    st.metric("Linhas do demonstrativo", ui.inteiro(len(df)))
    colunas = [c for c in ("conta", "coluna", "valor", "cod_conta") if c in df.columns]
    exibir = df[colunas] if colunas else df
    exibir = exibir.rename(columns={"conta": "Conta", "coluna": "Coluna",
                                    "valor": "Valor (R$)", "cod_conta": "Codigo"})
    ui.tabela(exibir, nome, altura=440, config={
        "Valor (R$)": st.column_config.NumberColumn(format="%.2f")})
