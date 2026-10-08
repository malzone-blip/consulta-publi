# -*- coding: utf-8 -*-
"""Penalidades aplicadas pelo Banco Central: inabilitados e proibidos."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "compliance"

QUADROS = {
    "Inabilitados": "QuadroGeralInabilitados",
    "Proibidos": "QuadroGeralProibidos",
}


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    f1, f2 = st.columns([0.32, 0.68])
    with f1:
        quadro = st.selectbox("Quadro", list(QUADROS.keys()))
    with f2:
        busca = st.text_input(
            "Consultar pessoa", placeholder="Nome completo ou parte do nome",
            help="O CPF e publicado parcialmente mascarado pelo proprio Banco Central.",
        )

    with st.spinner("Consultando o quadro de penalidades..."):
        df, resp = bcb.quadro_penalidades(QUADROS[quadro], forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "quadro de penalidades"):
        return
    if df.empty:
        ui.vazio("O quadro selecionado nao retornou registros.")
        return

    filtrado = df.copy()
    if busca:
        alvo = busca.strip().upper()
        filtrado = filtrado[
            filtrado["Nome"].astype(str).str.upper().str.contains(alvo, na=False)
        ]
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_COMPLIANCE",
                        "%s termo=%s resultados=%d"
                        % (quadro, busca.strip()[:80], len(filtrado)))
        if filtrado.empty:
            st.success(
                "Nenhum registro encontrado para '%s' no quadro de %s." % (busca, quadro),
                icon=":material/check_circle:",
            )
        else:
            st.error(
                "%d registro(s) encontrado(s) para '%s'. Confira nome e datas antes "
                "de concluir - homonimos existem." % (len(filtrado), busca),
                icon=":material/report:",
            )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Registros no quadro", ui.inteiro(len(df)))
    with c2:
        st.metric("Exibidos", ui.inteiro(len(filtrado)))
    with c3:
        if "Prazo_em_anos" in filtrado and not filtrado.empty:
            st.metric("Prazo medio da penalidade",
                      "%s anos" % ui.num(filtrado["Prazo_em_anos"].mean(), 1))

    st.write("")
    exibir = filtrado.rename(columns={
        "PAS": "Processo (PAS)", "Nome": "Nome", "CPF": "CPF",
        "Penalidade": "Penalidade", "Prazo_em_anos": "Prazo (anos)",
        "Inicio_do_cumprimento": "Inicio do cumprimento",
        "Prazo_final_penalidade": "Fim da penalidade"})
    ui.tabela(exibir, "penalidades_%s" % quadro.lower(), altura=460)

    ui.nota(
        "Fonte: quadros gerais de penalidades administrativas do Banco Central. "
        "Inabilitacao e proibicao impedem a pessoa de exercer cargo de administracao "
        "em instituicoes do sistema financeiro pelo prazo indicado. Este e um dado "
        "de apoio: a verificacao formal deve considerar tambem o CPF completo, que "
        "a fonte publica de forma mascarada."
    )
