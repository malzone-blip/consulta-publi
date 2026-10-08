# -*- coding: utf-8 -*-
"""NCM e Tarifa Externa Comum - classificacao de mercadorias no comercio exterior."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import fiscal

CHAVE = "ncm_tec"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()

    with st.spinner("Carregando a NCM oficial..."):
        df, resp, atualizacao = fiscal.ncm(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "NCM"):
        return
    if df.empty:
        ui.vazio("A NCM nao retornou itens.")
        return

    busca = st.text_input("Buscar produto ou codigo NCM",
                          placeholder="Ex.: 8471, cafe, veiculo",
                          key="busca_ncm")
    filtrado = fiscal.filtrar_ncm(df, busca)
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Itens na nomenclatura", ui.inteiro(len(df)))
    with c2:
        st.metric("Exibidos", ui.inteiro(len(filtrado)))
    if atualizacao:
        st.caption("Vigencia informada pela fonte: %s" % atualizacao)
    colunas = [c for c in ("Codigo", "Descricao", "Data_Inicio",
                           "Data_Fim") if c in filtrado.columns]
    ui.tabela(filtrado[colunas] if colunas else filtrado, "ncm_tec", altura=440)
    ui.nota(
        "A NCM classifica toda mercadoria no comercio exterior e na nota "
        "fiscal. Os oito digitos determinam aliquotas de II, IPI, PIS/"
        "COFINS e a Tarifa Externa Comum do Mercosul."
    )
