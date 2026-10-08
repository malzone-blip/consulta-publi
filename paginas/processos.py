# -*- coding: utf-8 -*-
"""Consulta processual no DataJud (CNJ) - todos os tribunais do pais."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import juridico

CHAVE = "processos"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()
    ui.cabecalho(modulo["titulo"], modulo["descricao"], None, atualizar, destino=topo)

    tribunais = juridico.TRIBUNAIS
    f1, f2 = st.columns([0.5, 0.5])
    with f1:
        alias = st.selectbox(
            "Tribunal", list(tribunais.keys()),
            index=list(tribunais.keys()).index("api_publica_tjsp"),
            format_func=lambda a: tribunais[a])
    with f2:
        numero = st.text_input("Numero do processo (opcional)",
                               placeholder="Numero unico CNJ ou so os digitos")

    with st.expander("Filtros adicionais", icon=":material/tune:"):
        c1, c2 = st.columns(2)
        with c1:
            classe = st.text_input("Classe processual", placeholder="Ex.: Execucao Fiscal")
            desde = st.text_input("Ajuizado a partir de", placeholder="AAAA-MM-DD")
        with c2:
            orgao = st.text_input("Orgao julgador", placeholder="Ex.: 1a Vara Civel")
            ate = st.text_input("Ajuizado ate", placeholder="AAAA-MM-DD")
        tamanho = st.select_slider("Quantidade de processos", [20, 50, 100, 200],
                                   value=50)

    consultar = st.button("Consultar processos", type="primary",
                          icon=":material/search:")

    # Guarda a ultima consulta para nao repetir a chamada a cada rerun.
    estado = "processos_%s" % alias
    if consultar:
        st.session_state[estado] = True
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_PROCESSO",
                        "tribunal=%s numero=%s" % (alias, numero.strip()[:30]))

    if not st.session_state.get(estado):
        ui.nota(
            "O DataJud reune os metadados processuais de todos os tribunais do pais, "
            "publicados pelo Conselho Nacional de Justica. Traz numero, classe, "
            "assuntos, orgao julgador e a linha do tempo de movimentos - nao o teor "
            "das pecas. Escolha o tribunal e clique em Consultar."
        )
        return

    with st.spinner("Consultando o DataJud..."):
        df, resp, total = juridico.processos(
            alias, numero.strip(), classe.strip(), orgao.strip(),
            desde.strip(), ate.strip(), tamanho, forcar)

    if not ui.verificar(resp, "DataJud"):
        return
    if df.empty:
        ui.vazio("Nenhum processo encontrado com esses criterios.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Processos exibidos", ui.inteiro(len(df)))
    with c2:
        st.metric("Total que atende ao filtro", ui.inteiro(total),
                  help="O tribunal pode ter mais processos do que os exibidos; "
                       "refine os filtros para chegar ao caso especifico.")

    ui.tabela(df, "processos_%s" % alias, altura=440)

    # Detalhe: linha do tempo de um processo
    if "Processo" in df and not df.empty:
        st.markdown("##### Linha do tempo de um processo")
        escolha = st.selectbox("Processo", df["Processo"].dropna().tolist())
        if escolha:
            with st.spinner("Carregando movimentos..."):
                mov, _ = juridico.movimentos_do_processo(alias, escolha, forcar)
            if mov is not None and not mov.empty:
                ui.tabela(mov, "movimentos_%s" % escolha, altura=340)
            else:
                ui.vazio("Sem movimentos registrados para este processo.")

    ui.nota(
        "Dados abertos processuais do CNJ. Processos em segredo de justica nao "
        "aparecem. A consulta e registrada na auditoria do sistema."
    )
