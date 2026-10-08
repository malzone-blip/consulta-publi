# -*- coding: utf-8 -*-
"""IBGE: territorio e indices oficiais."""
import streamlit as st

from core import auth, ui
from core.modulos import POR_CHAVE
from services import externas

CHAVE = "ibge"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    with st.spinner("Carregando dados do IBGE..."):
        estados, resp = externas.ibge_estados(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "localidades do IBGE"):
        return

    aba_territorio, aba_indices = st.tabs(["Territorio", "Indices"])

    with aba_territorio:
        if estados.empty:
            ui.vazio("Nao foi possivel carregar os estados.")
        else:
            c1, c2 = st.columns([0.3, 0.7])
            with c1:
                st.metric("Unidades da federacao", ui.inteiro(len(estados)))
            with c2:
                siglas = estados["sigla"].tolist()
                uf = st.selectbox(
                    "Ver municipios de", siglas,
                    index=siglas.index("SP") if "SP" in siglas else 0,
                    format_func=lambda s: "%s - %s" % (
                        s, estados[estados["sigla"] == s]["nome"].iloc[0]),
                )

            with st.spinner("Carregando municipios de %s..." % uf):
                municipios, r_mun = externas.ibge_municipios(uf, forcar)
            if not municipios.empty:
                st.metric("Municipios em %s" % uf, ui.inteiro(len(municipios)))
                colunas = {"id": "Codigo IBGE", "nome": "Municipio"}
                for c in municipios.columns:
                    if c.endswith("mesorregiao.nome"):
                        colunas[c] = "Mesorregiao"
                    if c.endswith("microrregiao.nome"):
                        colunas[c] = "Microrregiao"
                exibir = municipios.rename(columns=colunas)
                mostrar = [v for v in colunas.values() if v in exibir.columns]
                ui.tabela(exibir[mostrar] if mostrar else exibir,
                          "municipios_%s" % uf, altura=420)
                st.caption(r_mun.selo())
                ui.nota(
                    "O codigo IBGE do municipio e a chave que liga estes dados aos "
                    "cadastros do Banco Central: agencias, postos e correspondentes "
                    "trazem o mesmo codigo, o que permite cruzar as duas bases."
                )

    with aba_indices:
        nome = st.selectbox("Serie", list(externas.AGREGADOS_IBGE.keys()))
        cfg = externas.AGREGADOS_IBGE[nome]
        periodos = st.select_slider("Periodos", ["-6", "-12", "-24", "-48"],
                                    value="-24",
                                    format_func=lambda p: "%s meses" % p.strip("-"))
        with st.spinner("Consultando o SIDRA..."):
            df, r_ag = externas.ibge_agregado(cfg["agregado"], cfg["variavel"],
                                              periodos, "N1[all]", forcar)
        if ui.verificar(r_ag, "agregados do IBGE"):
            if df.empty:
                ui.vazio("Sem dados retornados para essa serie.")
            else:
                st.caption(r_ag.selo())
                serie = df.copy()
                serie["Periodo"] = serie["Periodo"].astype(str)
                st.line_chart(serie.set_index("Periodo")["Valor"], height=300,
                              color="#2563EB")
                ui.tabela(serie.sort_values("Periodo", ascending=False),
                          "ibge_%s" % cfg["agregado"], altura=320)
