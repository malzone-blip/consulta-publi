# -*- coding: utf-8 -*-
"""Ranking de qualidade das ouvidorias das instituicoes financeiras."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "ouvidorias"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Carregando periodos publicados..."):
        periodos, r_per = bcb.ouvidorias_periodos(forcar)

    if periodos.empty:
        ui.cabecalho(modulo["titulo"], modulo["descricao"], r_per, atualizar, destino=topo)
        ui.verificar(r_per, "periodos do ranking")
        ui.vazio("A fonte nao retornou periodos disponiveis.")
        return

    periodos = periodos.sort_values(["Ano", "Periodo"], ascending=False)
    rotulos = {
        "%s|%s|%s" % (r["Ano"], r["Periodo"], r["TipoPeriodo"]):
            "%s - %so %s" % (r["Ano"], r["Periodo"],
                             "semestre" if r["TipoPeriodo"] == "S" else "trimestre")
        for _, r in periodos.iterrows()
    }

    escolha = st.selectbox("Periodo de apuracao", list(rotulos.keys()),
                           format_func=lambda k: rotulos[k])
    ano, periodo, tipo = escolha.split("|")

    with st.spinner("Carregando ranking..."):
        df, resp = bcb.ouvidorias_relatorio(int(ano), int(periodo), tipo, forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "ranking de ouvidorias"):
        return
    if df.empty:
        ui.vazio("O Banco Central nao publicou dados para esse periodo. "
                 "Escolha outro na lista acima.")
        return

    st.metric("Instituicoes avaliadas", ui.inteiro(len(df)))
    st.write("")
    ui.tabela(df, "ouvidorias_%s_%s%s" % (ano, periodo, tipo), altura=480)

    ui.nota(
        "O ranking mede o desempenho das ouvidorias no tratamento das reclamacoes "
        "recebidas, e nao o volume de reclamacoes em si. A serie publicada e "
        "descontinua: nem todo periodo tem divulgacao."
    )
