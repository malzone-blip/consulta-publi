# -*- coding: utf-8 -*-
"""CNAE - Classificacao Nacional de Atividades Economicas."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import fiscal

CHAVE = "cnae"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    nivel = st.selectbox("Nivel", ["secoes", "divisoes", "grupos", "classes"],
                         index=3, format_func=str.capitalize)
    with st.spinner("Carregando CNAE..."):
        dfc, respc = fiscal.cnae(nivel, forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], respc, atualizar, destino=topo)
    if not ui.verificar(respc, "CNAE"):
        return
    if dfc.empty:
        ui.vazio()
        return

    busca = st.text_input("Buscar atividade", key="busca_cnae",
                          placeholder="Ex.: software, transporte")
    filtrado = dfc
    if busca and "descricao" in dfc:
        filtrado = dfc[dfc["descricao"].astype(str).str.upper()
                       .str.contains(busca.strip().upper(), na=False)]
    st.metric("Registros", ui.inteiro(len(filtrado)))
    ui.tabela(filtrado, "cnae_%s" % nivel, altura=420)
