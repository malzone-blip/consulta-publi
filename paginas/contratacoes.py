# -*- coding: utf-8 -*-
"""Contratacoes publicas - PNCP e catalogo Compras.gov.br."""
from datetime import date, timedelta

import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import governo

CHAVE = "contratacoes"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    aba_contratos, aba_atas, aba_editais, aba_catalogo = st.tabs(
        ["Contratos", "Atas de registro de preco", "Editais publicados", "Catalogo"])

    hoje = date.today()
    inicio_padrao = hoje - timedelta(days=10)

    with aba_contratos:
        c1, c2, c3 = st.columns(3)
        with c1:
            de = st.date_input("De", value=inicio_padrao, key="cont_de", format="DD/MM/YYYY")
        with c2:
            ate = st.date_input("Ate", value=hoje, key="cont_ate", format="DD/MM/YYYY")
        with c3:
            cnpj = st.text_input("CNPJ do orgao (opcional)", key="cont_cnpj")
        with st.spinner("Consultando o PNCP..."):
            df, resp, total = governo.pncp_contratos(de, ate, cnpj.strip(), 1, forcar)
        if ui.verificar(resp, "contratos do PNCP"):
            _mostrar(df, total, "pncp_contratos")

    with aba_atas:
        c1, c2 = st.columns(2)
        with c1:
            de = st.date_input("De", value=inicio_padrao, key="ata_de", format="DD/MM/YYYY")
        with c2:
            ate = st.date_input("Ate", value=hoje, key="ata_ate", format="DD/MM/YYYY")
        with st.spinner("Consultando o PNCP..."):
            dfa, respa, totala = governo.pncp_atas(de, ate, 1, forcar)
        if ui.verificar(respa, "atas do PNCP"):
            _mostrar(dfa, totala, "pncp_atas")

    with aba_editais:
        c1, c2, c3 = st.columns(3)
        with c1:
            de = st.date_input("De", value=inicio_padrao, key="edi_de", format="DD/MM/YYYY")
        with c2:
            ate = st.date_input("Ate", value=hoje, key="edi_ate", format="DD/MM/YYYY")
        with c3:
            modalidade = st.selectbox("Modalidade", list(governo.MODALIDADES.keys()),
                                      index=5,
                                      format_func=lambda m: governo.MODALIDADES[m])
        with st.spinner("Consultando o PNCP..."):
            dfe, respe, totale = governo.pncp_contratacoes(de, ate, modalidade, 1, forcar)
        if ui.verificar(respe, "editais do PNCP"):
            _mostrar(dfe, totale, "pncp_editais")

    with aba_catalogo:
        nivel = st.radio("Nivel", ["grupo", "classe"], horizontal=True,
                         format_func=str.capitalize)
        with st.spinner("Carregando catalogo..."):
            dfc, respc = governo.catalogo_material(nivel, 1, forcar)
        if ui.verificar(respc, "catalogo de material"):
            if dfc.empty:
                ui.vazio()
            else:
                busca = st.text_input("Filtrar", key="cat_busca")
                filtrado = dfc
                if busca:
                    col = next((c for c in dfc.columns if "nome" in c.lower()), None)
                    if col:
                        filtrado = dfc[dfc[col].astype(str).str.upper()
                                       .str.contains(busca.strip().upper(), na=False)]
                st.metric("Itens", ui.inteiro(len(filtrado)))
                ui.tabela(filtrado, "catalogo_%s" % nivel, altura=400)

    ui.nota(
        "O PNCP e o portal oficial de todas as contratacoes publicas sob a Lei "
        "14.133. Serve para acompanhar oportunidades de fornecimento ao governo e "
        "para conferir contratos ja firmados. Cada consulta traz uma pagina de ate "
        "500 registros no periodo."
    )


def _mostrar(df, total, nome):
    if df.empty:
        ui.vazio("Nenhum registro no periodo selecionado.")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Registros nesta pagina", ui.inteiro(len(df)))
    with c2:
        st.metric("Total no periodo", ui.inteiro(total))
    ui.tabela(df, nome, altura=430)
