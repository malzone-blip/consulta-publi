# -*- coding: utf-8 -*-
"""Diarios oficiais municipais - Querido Diario (Open Knowledge Brasil)."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import juridico

CHAVE = "diarios"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    c1, c2 = st.columns([0.4, 0.6])
    with c1:
        cidade = st.text_input("Municipio", placeholder="Ex.: Campinas",
                               value="")
    with c2:
        termo = st.text_input("Buscar no texto (opcional)",
                              placeholder="Ex.: nome da empresa, CNPJ, licitacao")

    c3, c4, c5 = st.columns(3)
    with c3:
        desde = st.text_input("A partir de", placeholder="AAAA-MM-DD")
    with c4:
        ate = st.text_input("Ate", placeholder="AAAA-MM-DD")
    with c5:
        st.write("")
        buscar = st.button("Buscar diarios", type="primary",
                           icon=":material/search:", use_container_width=True)

    if not cidade.strip():
        ui.nota(
            "O Querido Diario, mantido pela Open Knowledge Brasil, digitaliza e torna "
            "pesquisavel o texto dos diarios oficiais de centenas de municipios. "
            "Digite a cidade e, opcionalmente, um termo para buscar dentro das "
            "publicacoes - util para achar mencoes a empresas, contratos e editais."
        )
        return

    with st.spinner("Localizando o municipio..."):
        cidades, r_cid = juridico.cidades_diario(cidade.strip(), forcar)
    if not ui.verificar(r_cid, "municipios"):
        return
    if cidades.empty:
        ui.vazio("Municipio nao encontrado na base do Querido Diario. Nem toda "
                 "cidade tem diario digitalizado.")
        return

    mapa = {}
    for _, r in cidades.iterrows():
        rotulo = "%s / %s" % (r.get("territory_name", cidade),
                              r.get("state_code", ""))
        mapa[r.get("territory_id")] = rotulo
    territorio = st.selectbox("Confirme o municipio", list(mapa.keys()),
                              format_func=lambda t: mapa[t])

    if buscar or st.session_state.get("diarios_buscou"):
        st.session_state["diarios_buscou"] = True
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_DIARIO",
                        "municipio=%s termo=%s" % (mapa.get(territorio, ""),
                                                   termo.strip()[:60]))
        with st.spinner("Buscando publicacoes..."):
            df, resp, total = juridico.diarios(
                (territorio,), termo.strip(), desde.strip(), ate.strip(), 30, forcar)
        if not ui.verificar(resp, "diarios oficiais"):
            return
        if df.empty:
            ui.vazio("Nenhuma publicacao encontrada para esse periodo/termo.")
            return
        st.metric("Publicacoes encontradas", ui.inteiro(total))
        ui.tabela(df, "diarios_%s" % territorio, altura=440,
                  config={"Link": st.column_config.LinkColumn("Abrir PDF")})
        ui.nota(
            "Cada linha e uma edicao do diario oficial. O trecho mostra onde o termo "
            "buscado aparece; o link abre o PDF original da publicacao."
        )
