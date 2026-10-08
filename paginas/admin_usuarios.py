# -*- coding: utf-8 -*-
"""Administracao de usuarios e permissoes de acesso."""
import re
import sqlite3

import pandas as pd
import streamlit as st

from core import audit, auth, db, ui
from core.config import SENHA_PADRAO
from core.modulos import (DEPARTAMENTOS, POR_CHAVE, grupos_atribuiveis,
                          modulos_atribuiveis, modulos_do_departamento)

CHAVE = "admin_usuarios"


def render():
    auth.exigir(CHAVE)
    modulo = POR_CHAVE[CHAVE]
    eu = auth.usuario_atual()

    ui.cabecalho(modulo["titulo"], modulo["descricao"])
    auth.aviso_senha_padrao_admin()

    aba_lista, aba_novo = st.tabs(["Usuarios cadastrados", "Cadastrar usuario"])
    with aba_lista:
        _lista_e_edicao(eu)
    with aba_novo:
        _cadastro(eu)


# ---------------------------------------------------------------------------
def _rotulo_modulo(chave: str) -> str:
    m = POR_CHAVE.get(chave)
    return "%s - %s" % (m["grupo"], m["titulo"]) if m else chave


def _indice_setor(valor: str) -> int:
    """Posicao de 'valor' na lista fixa de setores; 0 (primeiro) se nao achar -
    cobre cadastros antigos gravados antes do setor virar lista fechada."""
    return DEPARTAMENTOS.index(valor) if valor in DEPARTAMENTOS else 0


def _lista_e_edicao(eu):
    usuarios = db.listar_usuarios()
    if not usuarios:
        ui.vazio("Nenhum usuario cadastrado.")
        return

    tabela = pd.DataFrame([{
        "Usuario": u["usuario"],
        "Nome": u["nome"],
        "Setor": u["setor"] or "-",
        "Perfil": "Administrador" if u["is_admin"] else "Usuario",
        "Situacao": "Ativo" if u["ativo"] else "Inativo",
        "Senha": "PADRAO" if u["deve_trocar_senha"] else "Definida",
        "Modulos": "todos" if u["is_admin"] else u["qtd_permissoes"],
        "Ultimo acesso": u["ultimo_login"] or "nunca",
    } for u in usuarios])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Usuarios", ui.inteiro(len(usuarios)))
    with c2:
        st.metric("Ativos", ui.inteiro(sum(1 for u in usuarios if u["ativo"])))
    with c3:
        st.metric("Administradores", ui.inteiro(sum(1 for u in usuarios if u["is_admin"])))
    with c4:
        st.metric("Na senha padrao",
                  ui.inteiro(sum(1 for u in usuarios if u["deve_trocar_senha"])))

    st.write("")
    ui.tabela(tabela, "usuarios_integrapublic", altura=300)

    st.markdown("##### Editar usuario")
    mapa = {u["id"]: "%s - %s" % (u["usuario"], u["nome"]) for u in usuarios}
    uid = st.selectbox("Selecione", list(mapa.keys()), format_func=lambda i: mapa[i])
    if uid:
        _form_edicao(uid, eu)


def _form_edicao(uid, eu):
    linha = db.buscar_usuario_id(uid)
    if not linha:
        st.warning("Usuario nao encontrado.")
        return

    atuais = db.permissoes_do_usuario(uid)
    chave_perm = "perm_edicao_%d" % uid
    todos = [m["chave"] for m in modulos_atribuiveis()]

    if chave_perm not in st.session_state:
        st.session_state[chave_perm] = sorted(atuais)

    # Os botoes ficam ANTES do formulario: assim podem ajustar a selecao
    # antes de o multiselect ser instanciado nesta mesma execucao.
    b1, b2, b3, _ = st.columns([0.18, 0.14, 0.22, 0.46])
    with b1:
        if st.button("Marcar todos", use_container_width=True, key="todos_%d" % uid):
            st.session_state[chave_perm] = todos
    with b2:
        if st.button("Limpar", use_container_width=True, key="limpar_%d" % uid):
            st.session_state[chave_perm] = []
    with b3:
        if st.button("Sugerir do setor", use_container_width=True, key="sugerir_%d" % uid,
                     help="Preenche com os modulos cadastrados para o setor atual "
                          "do usuario (%s)." % (linha["setor"] or "-")):
            sugestao = modulos_do_departamento(linha["setor"] or "")
            st.session_state[chave_perm] = sugestao or st.session_state[chave_perm]

    with st.form("editar_%d" % uid, border=True):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome completo", value=linha["nome"])
            email = st.text_input("E-mail", value=linha["email"] or "")
        with c2:
            setor = st.selectbox("Setor / departamento", DEPARTAMENTOS,
                                 index=_indice_setor(linha["setor"]))
            cc1, cc2 = st.columns(2)
            with cc1:
                is_admin = st.checkbox("Administrador", value=bool(linha["is_admin"]),
                                       help="Administradores acessam todos os modulos "
                                            "e a area administrativa.")
            with cc2:
                ativo = st.checkbox("Ativo", value=bool(linha["ativo"]))

        st.markdown("**Modulos liberados**")
        if is_admin:
            st.caption("Administrador tem acesso a todos os modulos por definicao. "
                       "A selecao abaixo fica guardada caso o perfil volte a comum.")
        modulos = st.multiselect(
            "Selecione os modulos", todos, key=chave_perm,
            format_func=_rotulo_modulo, label_visibility="collapsed",
        )

        s1, s2, s3 = st.columns(3)
        with s1:
            salvar = st.form_submit_button("Salvar alteracoes", type="primary",
                                           use_container_width=True)
        with s2:
            redefinir = st.form_submit_button("Redefinir senha", use_container_width=True)
        with s3:
            excluir = st.form_submit_button("Excluir usuario", use_container_width=True)

    if salvar:
        _salvar(uid, linha, nome, email, setor, is_admin, ativo, modulos, eu)
    if redefinir:
        _redefinir(uid, linha, eu)
    if excluir:
        st.session_state["confirmar_exclusao"] = uid

    if st.session_state.get("confirmar_exclusao") == uid:
        _confirmar_exclusao(uid, linha, eu)


def _salvar(uid, linha, nome, email, setor, is_admin, ativo, modulos, eu):
    if not nome.strip():
        st.error("O nome nao pode ficar em branco.", icon=":material/error:")
        return
    perdendo_admin = linha["is_admin"] and not is_admin
    desativando = linha["ativo"] and not ativo
    if (perdendo_admin or desativando) and db.contar_admins_ativos() <= 1 \
            and linha["is_admin"] and linha["ativo"]:
        st.error("Este e o unico administrador ativo. Promova outro usuario antes "
                 "de rebaixar ou desativar este.", icon=":material/shield:")
        return
    db.atualizar_usuario(uid, nome, email, setor, is_admin, ativo, modulos)
    audit.registrar(eu["usuario"], "USUARIO_EDITADO",
                    "alvo=%s admin=%s ativo=%s modulos=%d"
                    % (linha["usuario"], is_admin, ativo, len(modulos)))
    st.success("Alteracoes salvas.", icon=":material/check_circle:")
    st.rerun()


def _redefinir(uid, linha, eu):
    db.redefinir_para_senha_padrao(uid)
    audit.registrar(eu["usuario"], "SENHA_REDEFINIDA", "alvo=%s" % linha["usuario"])
    st.success(
        "Senha de **%s** redefinida para `%s`. O usuario tera de troca-la no "
        "proximo acesso." % (linha["usuario"], SENHA_PADRAO),
        icon=":material/key:",
    )


def _confirmar_exclusao(uid, linha, eu):
    if uid == eu["id"]:
        st.error("Voce nao pode excluir o proprio usuario.", icon=":material/block:")
        st.session_state.pop("confirmar_exclusao", None)
        return
    if linha["is_admin"] and linha["ativo"] and db.contar_admins_ativos() <= 1:
        st.error("Este e o unico administrador ativo e nao pode ser excluido.",
                 icon=":material/shield:")
        st.session_state.pop("confirmar_exclusao", None)
        return

    st.warning(
        "Confirma a exclusao definitiva de **%s** (%s)? As permissoes serao "
        "removidas junto. O historico de auditoria e preservado."
        % (linha["nome"], linha["usuario"]),
        icon=":material/delete_forever:",
    )
    c1, c2, _ = st.columns([0.2, 0.2, 0.6])
    with c1:
        if st.button("Sim, excluir", type="primary", use_container_width=True,
                     key="conf_sim_%d" % uid):
            db.excluir_usuario(uid)
            audit.registrar(eu["usuario"], "USUARIO_EXCLUIDO",
                            "alvo=%s" % linha["usuario"])
            st.session_state.pop("confirmar_exclusao", None)
            st.session_state.pop("perm_edicao_%d" % uid, None)
            st.success("Usuario excluido.")
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True, key="conf_nao_%d" % uid):
            st.session_state.pop("confirmar_exclusao", None)
            st.rerun()


# ---------------------------------------------------------------------------
def _cadastro(eu):
    st.caption(
        "O novo usuario e criado com a senha padrao **%s** e obrigado a troca-la "
        "no primeiro acesso." % SENHA_PADRAO
    )

    chave_perm = "perm_novo"
    todos = [m["chave"] for m in modulos_atribuiveis()]
    if chave_perm not in st.session_state:
        st.session_state[chave_perm] = todos

    c_setor, c_perfil = st.columns([0.26, 0.74])
    with c_setor:
        setor = st.selectbox("Setor / departamento", DEPARTAMENTOS, key="setor_novo")
    with c_perfil:
        perfil = st.radio(
            "Perfil de acesso",
            ["Sugerido para o setor", "Acesso completo aos dados",
             "Somente consulta basica", "Personalizado"],
            horizontal=True,
            help="Define a selecao inicial de modulos; voce pode ajustar antes de salvar. "
                 "'Sugerido para o setor' usa os modulos cadastrados para o setor "
                 "escolhido ao lado.",
        )
    if perfil == "Sugerido para o setor":
        sugestao = modulos_do_departamento(setor)
        st.session_state[chave_perm] = sugestao or todos
    elif perfil == "Acesso completo aos dados":
        st.session_state[chave_perm] = todos
    elif perfil == "Somente consulta basica":
        st.session_state[chave_perm] = [c for c in ("painel", "indicadores", "cambio",
                                                    "consultas") if c in todos]

    with st.form("novo_usuario", border=True, clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            usuario = st.text_input("Usuario de acesso *",
                                    placeholder="nome.sobrenome",
                                    help="Sem espacos ou acentos. Nao pode repetir.")
            nome = st.text_input("Nome completo *")
        with c2:
            email = st.text_input("E-mail")
            st.caption("Setor selecionado: **%s**" % setor)

        is_admin = st.checkbox(
            "Conceder perfil de administrador",
            help="Administradores gerenciam usuarios e veem todos os modulos.",
        )

        st.markdown("**Modulos liberados**")
        modulos = st.multiselect("Modulos", todos, key=chave_perm,
                                 format_func=_rotulo_modulo,
                                 label_visibility="collapsed")

        criar = st.form_submit_button("Criar usuario", type="primary",
                                      use_container_width=True)

    if criar:
        _criar(usuario, nome, email, setor, is_admin, modulos, eu)


def _criar(usuario, nome, email, setor, is_admin, modulos, eu):
    login = (usuario or "").strip().lower()
    if not login or not (nome or "").strip():
        st.error("Usuario e nome completo sao obrigatorios.", icon=":material/error:")
        return
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", login):
        st.error("O usuario deve ter de 3 a 40 caracteres, apenas letras minusculas, "
                 "numeros, ponto, hifen ou sublinhado.", icon=":material/error:")
        return
    if db.buscar_usuario(login):
        st.error("Ja existe um usuario com esse login.", icon=":material/error:")
        return
    try:
        db.criar_usuario(login, nome, email, setor, is_admin, modulos, eu["usuario"])
    except sqlite3.IntegrityError:
        st.error("Ja existe um usuario com esse login.", icon=":material/error:")
        return

    audit.registrar(eu["usuario"], "USUARIO_CRIADO",
                    "novo=%s admin=%s modulos=%d" % (login, is_admin, len(modulos)))
    st.success(
        "Usuario **%s** criado. Informe a senha inicial `%s` - o sistema exigira a "
        "troca no primeiro acesso." % (login, SENHA_PADRAO),
        icon=":material/check_circle:",
    )
