# -*- coding: utf-8 -*-
"""Trilha de auditoria do sistema."""
import pandas as pd
import streamlit as st

from core import audit, auth, ui
from core.modulos import POR_CHAVE

CHAVE = "admin_auditoria"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    ui.cabecalho(modulo["titulo"], modulo["descricao"])

    c1, c2, c3 = st.columns([0.34, 0.34, 0.32])
    with c1:
        usuario = st.text_input("Filtrar por usuario", placeholder="Parte do login")
    with c2:
        acoes = audit.acoes_distintas()
        acao = st.selectbox("Tipo de acao", ["(todas)"] + acoes)
    with c3:
        limite = st.select_slider("Registros", [100, 500, 1000, 5000], value=500)

    registros = audit.listar(limite, usuario.strip(),
                             "" if acao == "(todas)" else acao)
    if not registros:
        ui.vazio("Nenhum evento registrado com esses filtros.")
        return

    df = pd.DataFrame([{
        "Quando": r["quando"], "Usuario": r["usuario"],
        "Acao": r["acao"], "Detalhe": r["detalhe"],
    } for r in registros])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Eventos exibidos", ui.inteiro(len(df)))
    with c2:
        st.metric("Usuarios distintos", ui.inteiro(df["Usuario"].nunique()))
    with c3:
        falhas = int((df["Acao"] == "LOGIN_FALHA").sum())
        st.metric("Falhas de login", ui.inteiro(falhas),
                  help="Cinco falhas seguidas bloqueiam o acesso por 10 minutos.")

    st.write("")
    ui.tabela(df, "auditoria", altura=480)

    ui.nota(
        "A auditoria registra acessos, alteracoes de cadastro, redefinicoes de senha "
        "e consultas sensiveis (compliance, correspondentes, CNPJ). Os registros nao "
        "sao apagados quando um usuario e excluido."
    )
