# -*- coding: utf-8 -*-
"""Acompanhamento legislativo: Camara dos Deputados e Senado Federal."""
from datetime import date

import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import juridico

CHAVE = "legislativo"

TIPOS_PROPOSICAO = {"": "Todos", "PL": "Projeto de Lei", "PEC": "Emenda constitucional",
                    "PLP": "Lei complementar", "MPV": "Medida provisoria",
                    "PDL": "Decreto legislativo"}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    aba_camara, aba_senado, aba_parlamentares = st.tabs(
        ["Proposicoes - Camara", "Materias - Senado", "Parlamentares"])

    with aba_camara:
        c1, c2, c3 = st.columns(3)
        with c1:
            ano = st.selectbox("Ano", list(range(date.today().year, 2018, -1)),
                               key="cam_ano")
        with c2:
            tipo = st.selectbox("Tipo", list(TIPOS_PROPOSICAO.keys()),
                                format_func=lambda t: TIPOS_PROPOSICAO[t], key="cam_tipo")
        with c3:
            termo = st.text_input("Palavra-chave", key="cam_termo",
                                  placeholder="Ex.: tributo, saude")
        with st.spinner("Consultando a Camara..."):
            df, resp = juridico.proposicoes_camara(ano, tipo, termo.strip(), 100, forcar)
        if ui.verificar(resp, "proposicoes da Camara"):
            if df.empty:
                ui.vazio("Nenhuma proposicao para esses filtros.")
            else:
                st.metric("Proposicoes", ui.inteiro(len(df)))
                colunas = [c for c in ("siglaTipo", "numero", "ano", "ementa")
                           if c in df.columns]
                exibir = df[colunas].rename(columns={
                    "siglaTipo": "Tipo", "numero": "Numero", "ano": "Ano",
                    "ementa": "Ementa"}) if colunas else df
                ui.tabela(exibir, "camara_proposicoes_%s" % ano, altura=420)

    with aba_senado:
        c1, c2 = st.columns(2)
        with c1:
            ano_s = st.selectbox("Ano", list(range(date.today().year, 2018, -1)),
                                 key="sen_ano")
        with c2:
            sigla_s = st.selectbox("Tipo", ["PL", "PEC", "PLP", "MPV", "PDL"],
                                   key="sen_sigla")
        with st.spinner("Consultando o Senado..."):
            dfs, resps = juridico.materias_senado(ano_s, sigla_s, forcar)
        if ui.verificar(resps, "materias do Senado"):
            if dfs.empty:
                ui.vazio("Nenhuma materia para esses filtros.")
            else:
                st.metric("Materias", ui.inteiro(len(dfs)))
                ui.tabela(dfs, "senado_materias_%s" % ano_s, altura=420)

    with aba_parlamentares:
        sub = st.radio("Casa", ["Deputados", "Senadores"], horizontal=True)
        if sub == "Deputados":
            c1, c2 = st.columns(2)
            with c1:
                uf = st.text_input("UF", key="dep_uf", placeholder="Ex.: SP", max_chars=2)
            with c2:
                partido = st.text_input("Partido", key="dep_part",
                                        placeholder="Ex.: PT, PL")
            with st.spinner("Carregando deputados..."):
                dfd, respd = juridico.deputados(uf.strip().upper(),
                                                partido.strip().upper(), forcar)
            if ui.verificar(respd, "deputados") and not dfd.empty:
                colunas = [c for c in ("nome", "siglaPartido", "siglaUf", "email")
                           if c in dfd.columns]
                exibir = dfd[colunas].rename(columns={
                    "nome": "Nome", "siglaPartido": "Partido", "siglaUf": "UF",
                    "email": "E-mail"}) if colunas else dfd
                st.metric("Deputados", ui.inteiro(len(exibir)))
                ui.tabela(exibir, "deputados", altura=400)
        else:
            with st.spinner("Carregando senadores..."):
                dfsen, respsen = juridico.senadores(forcar)
            if ui.verificar(respsen, "senadores") and not dfsen.empty:
                st.metric("Senadores em exercicio", ui.inteiro(len(dfsen)))
                ui.tabela(dfsen[["Nome", "Partido", "UF", "E-mail"]]
                          if "Nome" in dfsen else dfsen, "senadores", altura=400)

    ui.nota(
        "Fontes: Dados Abertos da Camara dos Deputados e do Senado Federal. "
        "Util para o Juridico acompanhar projetos que afetem o setor da empresa."
    )
