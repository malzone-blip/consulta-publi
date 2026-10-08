# -*- coding: utf-8 -*-
"""IntegraPublic - Sistema Geral Interdepartamental.

Ponto de entrada. Executar sempre pelo ambiente virtual do projeto:

    .venv\\Scripts\\python.exe -m streamlit run app.py

O menu lateral e montado dinamicamente a partir das permissoes do usuario
logado: cada pessoa ve apenas os modulos liberados para ela.
"""
import importlib

import streamlit as st

from core import auth, db, ui
from core.config import APP_NOME, APP_SUBTITULO
from core.modulos import MODULOS, ORDEM_GRUPOS

st.set_page_config(
    page_title=APP_NOME,
    page_icon=":material/hub:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"about": "%s - %s" % (APP_NOME, APP_SUBTITULO)},
)

db.inicializar()
ui.injetar_css()

# --- porteiro -------------------------------------------------------------
usuario = auth.usuario_atual()
if usuario is None:
    auth.tela_login()
    st.stop()

if usuario["deve_trocar_senha"]:
    auth.tela_trocar_senha_obrigatoria()
    st.stop()

# --- monta o menu conforme as permissoes ----------------------------------
permitidos = auth.permissoes()
secoes = {}
falhas = []

for grupo in ORDEM_GRUPOS:
    paginas = []
    for modulo in MODULOS:
        if modulo["grupo"] != grupo or modulo["chave"] not in permitidos:
            continue
        if modulo.get("somente_admin") and not usuario["is_admin"]:
            continue
        # Modulo que depende de chave de API so aparece quando a chave existe.
        # O administrador continua vendo (para saber que precisa configura-la).
        chave_exigida = modulo.get("requer_chave")
        if chave_exigida and not db.obter_config(chave_exigida, "") \
                and not usuario["is_admin"]:
            continue
        try:
            carregado = importlib.import_module("paginas.%s" % modulo["arquivo"])
            paginas.append(st.Page(
                carregado.render,
                title=modulo["titulo"],
                icon=modulo["icone"],
                url_path=modulo["chave"],
            ))
        except Exception as exc:  # um modulo com defeito nao derruba o sistema
            falhas.append("%s (%s: %s)" % (modulo["titulo"], type(exc).__name__, exc))
    if paginas:
        secoes[grupo] = paginas

ui.marca_lateral()

if not secoes:
    st.warning(
        "Seu usuario ainda nao possui nenhum modulo liberado. Peca ao administrador "
        "do sistema para conceder acesso em Administracao > Usuarios e Permissoes.",
        icon=":material/lock:",
    )
    ui.rodape_lateral(usuario)
    if st.sidebar.button("Sair", use_container_width=True, icon=":material/logout:"):
        auth.sair()
    st.stop()

# expanded=True evita que o Streamlit esconda parte dos modulos atras de um
# "ver mais": com 21 telas, o menu precisa estar todo visivel de uma vez.
navegacao = st.navigation(secoes, position="sidebar", expanded=True)

# --- rodape da barra lateral ----------------------------------------------
st.sidebar.divider()
ui.rodape_lateral(usuario)
auth.bloco_trocar_senha()
if st.sidebar.button("Sair", use_container_width=True, icon=":material/logout:"):
    auth.sair()

if falhas:
    st.sidebar.error("Modulos com erro de carga:\n\n- %s" % "\n- ".join(falhas))

navegacao.run()
