# -*- coding: utf-8 -*-
"""Dominios de internet verificados das instituicoes financeiras."""
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE
from services import bcb

CHAVE = "dominios"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    forcar, atualizar = ui.controle_atualizacao(CHAVE)
    topo = st.container()  # cabecalho fica no topo, preenchido apos a consulta

    busca = st.text_input(
        "Verificar dominio ou instituicao",
        placeholder="Ex.: bb.com.br, itau, nubank",
        help="Digite o endereco que voce recebeu para conferir se ele consta como "
             "dominio oficial de alguma instituicao autorizada.",
    )

    with st.spinner("Carregando dominios verificados..."):
        df, resp = bcb.dominios_verificados(forcar)

    ui.cabecalho(modulo["titulo"], modulo["descricao"], resp, atualizar, destino=topo)
    if not ui.verificar(resp, "dominios verificados"):
        return
    if df.empty:
        ui.vazio("A fonte nao retornou dominios.")
        return

    filtrado = df.copy()
    if busca:
        alvo = busca.strip().lower().replace("https://", "").replace("http://", "")
        alvo = alvo.split("/")[0]
        mascara = (
            filtrado["DOMINIO"].astype(str).str.lower().str.contains(alvo, na=False)
            | filtrado["INSTITUICAO_FINANCEIRA"].astype(str).str.lower().str.contains(
                alvo, na=False)
        )
        filtrado = filtrado[mascara]
        audit.registrar(auth.usuario_atual()["usuario"], "CONSULTA_DOMINIO",
                        "termo=%s resultados=%d" % (alvo[:80], len(filtrado)))
        if filtrado.empty:
            st.warning(
                "Nenhum dominio oficial corresponde a '%s'. Isso NAO confirma fraude, "
                "mas tambem nao confirma legitimidade - trate com desconfianca e "
                "confirme por canal oficial da instituicao." % busca,
                icon=":material/gpp_maybe:",
            )
        else:
            st.success(
                "%d correspondencia(s) na base oficial do Banco Central."
                % len(filtrado), icon=":material/verified:",
            )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Dominios cadastrados", ui.inteiro(len(df)))
    with c2:
        st.metric("Instituicoes", ui.inteiro(df["INSTITUICAO_FINANCEIRA"].nunique()))
    with c3:
        st.metric("Exibidos", ui.inteiro(len(filtrado)))

    st.write("")
    exibir = filtrado.copy()
    for coluna in ("CNPJ", "CNPJ_NO_REGISTRO_DO_DOMINIO"):
        if coluna in exibir:
            exibir[coluna] = exibir[coluna].map(ui.cnpj_formatado)
    exibir = exibir.rename(columns={
        "INSTITUICAO_FINANCEIRA": "Instituicao", "DOMINIO": "Dominio",
        "TIPO_DE_DOMINIO": "Tipo", "CONGLOMERADO": "Conglomerado",
        "PROPRIETARIO_DO_DOMINIO": "Proprietario do dominio",
        "CNPJ_NO_REGISTRO_DO_DOMINIO": "CNPJ no registro"})
    ordem = [c for c in ("Dominio", "Instituicao", "CNPJ", "Tipo", "Conglomerado",
                         "Proprietario do dominio", "CNPJ no registro")
             if c in exibir.columns]
    ui.tabela(exibir[ordem] if ordem else exibir, "dominios_verificados", altura=460)

    ui.nota(
        "Cada instituicao declara ao Banco Central os enderecos de internet que "
        "realmente usa. E a checagem mais rapida contra sites falsos: se o dominio "
        "do link nao esta aqui, ele nao e canal oficial declarado."
    )
